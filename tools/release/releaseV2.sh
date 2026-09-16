#!/usr/bin/env bash

# Copyright (c) 2026 Element Creations Ltd.
#
# SPDX-License-Identifier: AGPL-3.0-only.
# Please see LICENSE files in the repository root for full details.

# do not exit when any command fails, failures are handled explicitly by the script
set +e

gitHubRepo="seventwos-app/usr-workspace-android"
applicationId="org.seventwos.workspace"
productName="Seventwos Workspace for Android"

printf "\n================================================================================\n"
printf "|                  Welcome to the release script (V2)!                         |\n"
printf "================================================================================\n"

printf "Checking environment...\n"
envError=0

# Check that bundletool is installed
if ! command -v bundletool &> /dev/null
then
    printf "Fatal: bundletool is not installed. You can install it running \`brew install bundletool\`\n"
    envError=1
fi

# Check that the GitHub CLI is installed. It is expected to be already authenticated, see `gh auth login`.
if ! command -v gh &> /dev/null
then
    printf "Fatal: gh (the GitHub CLI) is not installed. You can install it running \`brew install gh\`\n"
    envError=1
fi

# Android home
androidHome="${ANDROID_HOME}"
if [[ -z "${androidHome}" ]]; then
    printf "Fatal: ANDROID_HOME is not defined in the environment.\n"
    envError=1
fi
# Matrix token used to announce the release / Not mandatory
releaseBotToken="${SEVENTWOS_RELEASE_MATRIX_TOKEN}"
if [[ -z "${releaseBotToken}" ]]; then
    printf "Warning: SEVENTWOS_RELEASE_MATRIX_TOKEN is not defined in the environment.\n"
fi
# Matrix room to announce the release to / Only used when the token above is defined
releaseRoomId="${SEVENTWOS_RELEASE_MATRIX_ROOM_ID}"
# Matrix homeserver used to send the announcement / Only used when the token above is defined
releaseHomeserver="${SEVENTWOS_RELEASE_MATRIX_HOMESERVER}"

if [ ${envError} == 1 ]; then
  exit 1
fi

# Abort the script with an error message.
fail() {
  printf "\nFatal: %s\n" "$1"
  exit 1
}

# Handle the result of a version check. ${checkError} must be set to 1 when a check has failed.
checkVersionResult() {
  if [[ ${checkError} -ne 0 ]]; then
    printf "\nThe check above has failed, this is not expected.\n"
    read -r -p "Do you want to continue anyway (yes/no) default to no? " doContinue
    doContinue=${doContinue:-no}
    if [ "${doContinue}" != "yes" ]; then
      exit 1
    fi
  else
    printf "The versions are correct.\n"
  fi
}

# Read minSdkVersion from file plugins/src/main/kotlin/Versions.kt
minSdkVersion=$(grep "MIN_SDK_FOSS =" ./plugins/src/main/kotlin/Versions.kt |cut -d '=' -f 2 |xargs)
# Read buildToolsVersion from file plugins/src/main/kotlin/Versions.kt
buildToolsVersion=$(grep "BUILD_TOOLS_VERSION =" ./plugins/src/main/kotlin/Versions.kt |cut -d '=' -f 2 |xargs)
buildToolsPath="${androidHome}/build-tools/${buildToolsVersion}"

if [[ ! -d ${buildToolsPath} ]]; then
    printf "Fatal: %s folder not found, ensure that you have installed the SDK version %s.\n" "${buildToolsPath}" "${buildToolsVersion}"
    exit 1
fi

# Check that there is no unmerged PR with the label "Z-NextRelease", else exit
unmergedPrs=$(gh pr list --repo "${gitHubRepo}" --label "Z-NextRelease" --state open --json title,url -q '.[] | "\(.url): \(.title)"')
if [[ ${unmergedPrs} != "" ]]; then
    printf "Fatal: There are unmerged PRs with the label Z-NextRelease:\n%s" "${unmergedPrs}"
    printf "\n"
    exit 1
fi


printf "OK\n"

printf "\n================================================================================\n"
printf "Ensuring main and develop branches are up to date...\n"

git checkout main
git pull
git checkout develop
git pull

printf "\n================================================================================\n"
# Guessing version to propose a default version
versionsFile="./plugins/src/main/kotlin/Versions.kt"
# The version of the release must match the date of next monday, where the release is supposed to go live
# The command below gets the date of next monday
nextMondayDateCommand="date -v +1w -v -monday"
# Get release year on 2 digits
versionYearCandidate=$(${nextMondayDateCommand} +%y)
currentVersionMonth=$(grep "val versionMonth" ${versionsFile} | cut  -d " " -f6)
# Get release month on 2 digits
versionMonthCandidate=$(${nextMondayDateCommand} +%m)
versionMonthCandidateNoLeadingZero=${versionMonthCandidate/#0/}
currentVersionReleaseNumber=$(grep "val versionReleaseNumber" ${versionsFile} | cut  -d " " -f6)
# if the release month is the same as the current version, we increment the release number, else we reset it to 0
if [[ ${currentVersionMonth} -eq ${versionMonthCandidateNoLeadingZero} ]]; then
  versionReleaseNumberCandidate=$((currentVersionReleaseNumber + 1))
else
  versionReleaseNumberCandidate=0
fi
versionCandidate="${versionYearCandidate}.${versionMonthCandidate}.${versionReleaseNumberCandidate}"

read -r -p "Please enter the release version (example: ${versionCandidate}). Format must be 'YY.MM.x' or 'YY.MM.xy', with year and month matching next Monday. Just press enter if ${versionCandidate} is correct. " version
version=${version:-${versionCandidate}}

# extract year, month and release number for future use
versionYear=$(echo "${version}" | cut  -d "." -f1)
versionMonth=$(echo "${version}" | cut  -d "." -f2)
versionMonthNoLeadingZero=${versionMonth/#0/}
versionReleaseNumber=$(echo "${version}" | cut  -d "." -f3)

printf "\n================================================================================\n"
printf "Starting the release %s\n" "${version}"
git checkout -b "release/${version}" develop

# Note: in case the release is already started and the script is started again, checkout the release branch again.
ret=$?
if [[ $ret -ne 0 ]]; then
  printf "Mmh, it seems that the release is already started. I'm displaying the changes now:\n"
  git diff --stat "release/${version}" origin/main
  printf "Do you want to continue the release using its contents?\n\n"
  read -r -p "Continue (yes/no) default to yes? " doContinue
  doContinue=${doContinue:-yes}
  if [ "${doContinue}" == "no" ]; then
    printf "OK, exiting, you can start the release again with the command 'git checkout -b release/%s develop'\n" "${version}"
    exit 1
  fi
  git checkout "release/${version}"
fi

# Ensure version is OK
versionsFileBak="${versionsFile}.bak"
cp ${versionsFile} ${versionsFileBak}
sed "s/private const val versionYear = .*/private const val versionYear = ${versionYear}/" ${versionsFileBak} > ${versionsFile}
sed "s/private const val versionMonth = .*/private const val versionMonth = ${versionMonthNoLeadingZero}/" ${versionsFile}    > ${versionsFileBak}
sed "s/private const val versionReleaseNumber = .*/private const val versionReleaseNumber = ${versionReleaseNumber}/" ${versionsFileBak} > ${versionsFile}
rm ${versionsFileBak}

printf -v versionReleaseNumber2Digits "%02d" "${versionReleaseNumber}"
versionCode="20${versionYear}${versionMonth}${versionReleaseNumber2Digits}0"

# Update the file aaptDump.txt with the new version
aaptDumpFile="./tools/manifest/gplay/release/aaptDump.txt"
sed "s/versionCode='[0-9]*'/versionCode='${versionCode}'/" ${aaptDumpFile} > ${aaptDumpFile}.bak
sed "s/versionName='[0-9]*\.[0-9]*\.[0-9]*'/versionName='${version}'/" ${aaptDumpFile}.bak > ${aaptDumpFile}
rm ${aaptDumpFile}.bak

git commit -a -m "Setting version for the release ${version}"

printf "\n================================================================================\n"
printf "Creating fastlane file...\n"
fastlaneFile="${versionCode}.txt"
fastlanePathFile="./fastlane/metadata/android/en-US/changelogs/${fastlaneFile}"
printf "Main changes in this version: bug fixes and improvements.\nFull changelog: https://github.com/%s/releases" "${gitHubRepo}" > "${fastlanePathFile}"

read -r -p "I have created the file ${fastlanePathFile}, please edit it and press enter to continue. "
git add "${fastlanePathFile}"
git commit -a -m "Adding fastlane file for version ${version}"

printf "\n================================================================================\n"
printf "OK, finishing the release...\n"
# Merge the release branch into main, tag it, then merge the tag back into develop and delete the
# release branch. The merge messages are provided explicitly to keep the history consistent with
# the previous releases.
git checkout main || fail "unable to checkout main."
git merge --no-ff --no-edit -m "Merge branch 'release/${version}'" "release/${version}" \
  || fail "unable to merge the branch release/${version} into main. Please fix the conflicts and finish the release manually."
git tag -a "v${version}" -m "Release v${version}" || fail "unable to create the tag v${version}."
git checkout develop || fail "unable to checkout develop."
git merge --no-ff --no-edit -m "Merge tag 'v${version}' into develop" "v${version}" \
  || fail "unable to merge the tag v${version} into develop. Please fix the conflicts and finish the release manually."
git branch -d "release/${version}" || fail "unable to delete the branch release/${version}."

printf "\n================================================================================\n"
read -r -p "Done, push the branch 'main', the new tag and the branch 'develop' (yes/no) default to yes? " doPush
doPush=${doPush:-yes}

if [ "${doPush}" == "yes" ]; then
  printf "Pushing branch 'main', tag 'v%s' and branch 'develop'...\n" "${version}"
  git push origin main
  git push origin "v${version}"
  git push origin develop
else
    printf "Not pushing, do not forget to push manually!\n"
fi

printf "\n================================================================================\n"
printf "Checking out develop...\n"
git checkout develop

printf "\n================================================================================\n"
printf "Building the release artifacts...\n"

targetPath="./tmp/seventwos-workspace/${version}"
artifactPath="${targetPath}/artifact"
# Paths inside the artifact, relative to the `app/build/outputs` folder uploaded by the workflow.
fdroidTargetPath="${artifactPath}/apk/fdroid/release"
gplayTargetPath="${artifactPath}/bundle/gplayRelease"

# The workflow release.yml is manually dispatched and only runs on the branch develop, so the run is
# identified by the head commit of develop, not by the release tag.
releaseCommit=$(git rev-parse --verify --quiet "develop^{commit}")
if [[ -z "${releaseCommit}" ]]; then
  # Without a commit, `gh run list` would return the latest run of the workflow, which may be another one.
  printf "Fatal: the branch develop cannot be resolved.\n"
  exit 1
fi

printf "Dispatching the workflow release.yml on the branch develop (commit %s)...\n" "${releaseCommit}"
gh workflow run release.yml --repo "${gitHubRepo}" --ref develop \
  || fail "unable to dispatch the workflow release.yml. Note that the run must be approved in the 'android-release' environment."

printf "Looking for the run of the workflow release.yml for the commit %s...\n" "${releaseCommit}"

runId=""

# The run can take a few seconds to appear after the dispatch, so retry for a couple of minutes.
for _ in $(seq 1 12); do
  runId=$(gh run list --repo "${gitHubRepo}" --workflow release.yml --commit "${releaseCommit}" --limit 1 --json databaseId -q '.[0].databaseId' 2> /dev/null)
  if [[ -n "${runId}" ]]; then
    break
  fi
  printf "No run found yet, waiting...\n"
  sleep 10
done

if [[ -z "${runId}" ]]; then
  printf "Fatal: no run of the workflow release.yml found for the commit %s.\n" "${releaseCommit}"
  exit 1
fi

printf "Found the run https://github.com/%s/actions/runs/%s\n" "${gitHubRepo}" "${runId}"
printf "Waiting for the run to complete. It may be waiting for a review of the 'android-release' environment...\n"
gh run watch "${runId}" --repo "${gitHubRepo}" --compact --exit-status

printf "\n================================================================================\n"
printf "Downloading the artifacts...\n"

# The workflow uploads a single artifact containing both the Gplay app bundle and the F-Droid APKs,
# already signed with the release key.
artifactName="seventwos-workspace-android-${releaseCommit}"

ret=1

while [[ $ret -ne 0 ]]; do
  gh run download "${runId}" --repo "${gitHubRepo}" \
     --dir "${artifactPath}" \
     --name "${artifactName}"

  ret=$?
  if [[ $ret -ne 0 ]]; then
    read -r -p "Error while downloading the artifact ${artifactName}. You may want to fix the issue and retry. Retry (yes/no) default to yes? " doRetry
    doRetry=${doRetry:-yes}
    if [ "${doRetry}" == "no" ]; then
      exit 1
    fi
  fi
done

printf "\n================================================================================\n"
printf "Checking the signed APKs...\n"

checkError=0

# Each APK gets the version code of the app bundle, plus the code of its ABI.
# Must be kept in sync with the abiVersionCodes map in app/build.gradle.kts.
fdroidAbis="armeabi-v7a:1 arm64-v8a:2 x86:3 x86_64:4"

for abiEntry in ${fdroidAbis}; do
  abi="${abiEntry%%:*}"
  abiCode="${abiEntry##*:}"
  expectedApkVersionCode=$((versionCode + abiCode))
  apkFile="${fdroidTargetPath}/app-fdroid-${abi}-release.apk"
  apkBadging=$("${buildToolsPath}"/aapt dump badging "${apkFile}" | grep -m 1 "^package")
  apkVersionCode=$(printf "%s" "${apkBadging}" | sed -n "s/.*versionCode='\([0-9]*\)'.*/\1/p")
  apkVersionName=$(printf "%s" "${apkBadging}" | sed -n "s/.*versionName='\([^']*\)'.*/\1/p")
  apkPackageName=$(printf "%s" "${apkBadging}" | sed -n "s/.*name='\([^']*\)'.*/\1/p")
  printf "File app-fdroid-%s-release.apk: package %s, version code %s, version name %s\n" "${abi}" "${apkPackageName}" "${apkVersionCode}" "${apkVersionName}"
  if [[ "${apkPackageName}" != "${applicationId}" ]]; then
    printf "Warning: was expecting the package %s, but got %s.\n" "${applicationId}" "${apkPackageName}"
    checkError=1
  fi
  if [[ "${apkVersionCode}" != "${expectedApkVersionCode}" ]]; then
    printf "Warning: was expecting the version code %s, but got %s.\n" "${expectedApkVersionCode}" "${apkVersionCode}"
    checkError=1
  fi
  if [[ "${apkVersionName}" != "${version}" ]]; then
    printf "Warning: was expecting the version name %s, but got %s.\n" "${version}" "${apkVersionName}"
    checkError=1
  fi
  apkCerts=$("${buildToolsPath}"/apksigner verify --min-sdk-version "${minSdkVersion}" --verbose --print-certs "${apkFile}")
  if [[ $? -ne 0 ]]; then
    printf "Warning: the signature of %s could not be verified.\n" "${apkFile}"
    checkError=1
  fi
  if printf "%s" "${apkCerts}" | grep -qi "Android Debug"; then
    printf "Warning: %s is signed with the Android debug certificate.\n" "${apkFile}"
    checkError=1
  fi
done

checkVersionResult

printf "\n================================================================================\n"
printf "The APKs in %s are signed and verified!\n" "${fdroidTargetPath}"

signedBundlePath="${gplayTargetPath}/app-gplay-release.aab"
# The universal APK is downloaded manually from the GooglePlay console, and is named after the version code.
universalApkPath="${gplayTargetPath}/${versionCode}.apk"

printf "\n================================================================================\n"
printf "Checking the signed app bundle...\n"

checkError=0

jarsigner -verify "${signedBundlePath}"
if [[ $? -ne 0 ]]; then
  printf "Warning: the signature of %s could not be verified.\n" "${signedBundlePath}"
  checkError=1
fi

bundleVersionCode=$(bundletool dump manifest --bundle="${signedBundlePath}" --xpath=/manifest/@android:versionCode)
bundleVersionName=$(bundletool dump manifest --bundle="${signedBundlePath}" --xpath=/manifest/@android:versionName)
printf "File %s: version code %s, version name %s\n" "$(basename "${signedBundlePath}")" "${bundleVersionCode}" "${bundleVersionName}"
if [[ "${bundleVersionCode}" != "${versionCode}" ]]; then
  printf "Warning: was expecting the version code %s, but got %s.\n" "${versionCode}" "${bundleVersionCode}"
  checkError=1
fi
if [[ "${bundleVersionName}" != "${version}" ]]; then
  printf "Warning: was expecting the version name %s, but got %s.\n" "${version}" "${bundleVersionName}"
  checkError=1
fi

checkVersionResult

printf "\n================================================================================\n"
printf "The file %s is signed and can be uploaded to the PlayStore!\n" "${signedBundlePath}"

printf "\n================================================================================\n"
read -r -p "Do you want to build the APKs from the app bundle? You need to do this step if you want to install the application to your device. (yes/no) default to no " doBuildApks
doBuildApks=${doBuildApks:-no}

if [ "${doBuildApks}" == "yes" ]; then
  printf "Building apks...\n"
  bundletool build-apks --bundle="${signedBundlePath}" --output="${gplayTargetPath}"/seventwos-workspace.apks \
      --ks=./app/signature/debug.keystore --ks-pass=pass:android --ks-key-alias=androiddebugkey --key-pass=pass:android \
      --overwrite

  read -r -p "Do you want to install the application to your device? Make sure there is one (and only one!) connected device first. (yes/no) default to yes " doDeploy
  doDeploy=${doDeploy:-yes}
  if [ "${doDeploy}" == "yes" ]; then
    printf "Installing apk for your device...\n"
    bundletool install-apks --apks="${gplayTargetPath}"/seventwos-workspace.apks
    read -r -p "Please run the application on your phone to check that the upgrade went well. Press enter to continue. "
  else
    printf "APK will not be deployed!\n"
  fi
else
  printf "APKs will not be generated!\n"
fi

printf "\n================================================================================\n"
printf "Create the open testing release on GooglePlay.\n"

printf "On GooglePlay console, go the the open testing section and click on \"Create new release\" button, then:\n"
printf " - upload the file %s.\n" "${signedBundlePath}"
printf " - copy the release note from the fastlane file.\n"
printf " - download the universal APK, to be able to provide it to the GitHub release: click on the right arrow next to the \"App bundle\", then click on the \"Download\" tab, and download the \"Signed, universal APK\". Save it, without renaming it, to the folder %s. The expected final path is %s\n" "${gplayTargetPath}" "${universalApkPath}"
printf " - submit the release.\n"
read -r -p "Press enter to continue. "

printf "You can then go to \"Publishing overview\" and send the new release for a review by Google.\n"
read -r -p "Press enter to continue. "

printf "\n================================================================================\n"
printf "Creating the release on GitHub.\n"

releaseAssets=(
  "${signedBundlePath}"
  "${universalApkPath}"
  "${fdroidTargetPath}/app-fdroid-arm64-v8a-release.apk"
  "${fdroidTargetPath}/app-fdroid-armeabi-v7a-release.apk"
  "${fdroidTargetPath}/app-fdroid-x86-release.apk"
  "${fdroidTargetPath}/app-fdroid-x86_64-release.apk"
)

# Set this variable to something other than 0 to enter the loop, and reset it to 0 when all files are found.
missingAsset=-1

while [[ ${missingAsset} -ne 0 ]]; do
  missingAsset=0
  for releaseAsset in "${releaseAssets[@]}"; do
    if [[ ! -f "${releaseAsset}" ]]; then
      printf "Error: the file %s does not exist.\n" "${releaseAsset}"
      missingAsset=1
    fi
  done

  if [[ ${missingAsset} -ne 0 ]]; then
    read -r -p "Some files are missing, please fix the issue and press enter to retry. Press Ctrl+C to exit. "
  fi
done

printf "Creating the pre-release v%s and uploading the %d files, this can take a while...\n" "${version}" "${#releaseAssets[@]}"
gh release create "v${version}" \
   --repo "${gitHubRepo}" \
   --title "${productName} v${version}" \
   --generate-notes \
   --prerelease \
   --verify-tag \
   "${releaseAssets[@]}"

if [[ $? -ne 0 ]]; then
  printf "Fatal: error while creating the GitHub release.\n"
  exit 1
fi

printf "The pre-release has been created: https://github.com/%s/releases/tag/v%s\n" "${gitHubRepo}" "${version}"
printf "Please check the generated release notes, and optionally reorder items and fix typos.\n"
read -r -p "Press enter to continue. "

printf "\n================================================================================\n"
printf "Update the project release notes:\n\n"

printf "Getting the release notes from GitHub...\n"
releaseNotes=$(gh release view "v${version}" --repo "${gitHubRepo}" --json body -q .body)

if [[ $? -ne 0 || -z "${releaseNotes}" ]]; then
  printf "Fatal: error while getting the release notes from GitHub.\n"
  exit 1
fi

# GitHub returns the release notes with CRLF line endings, remove the CR.
releaseNotes="${releaseNotes//$'\r'/}"
changesTitle="Changes in ${productName} v${version}"
# Underline the title with as many '=' as there are characters in the title.
changesUnderline="${changesTitle//?/=}"
changesFile="./CHANGES.md"
changesFileBak="${changesFile}.bak"
mv "${changesFile}" "${changesFileBak}"
{
  printf "%s\n%s\n\n" "${changesTitle}" "${changesUnderline}"
  printf "%s\n\n" "${releaseNotes}"
  cat "${changesFileBak}"
} > "${changesFile}"
rm "${changesFileBak}"
printf "The file CHANGES.md has been updated.\n"
read -r -p "Please check the change and press enter to commit it. "

printf "\n================================================================================\n"
printf "Committing...\n"
git commit -a -m "Changelog for version ${version}"

printf "\n================================================================================\n"
read -r -p "Done, push the branch 'develop' (yes/no) default to yes? (A rebase may be necessary in case develop got new commits) " doPush
doPush=${doPush:-yes}

if [ "${doPush}" == "yes" ]; then
  printf "Pushing branch 'develop'...\n"
  git push origin develop
else
    printf "Not pushing, do not forget to push manually!\n"
fi

printf "\n================================================================================\n"
printf "Message for the Android internal room:\n\n"
message="@room ${productName} ${version} is ready to be tested. You can get it from https://github.com/${gitHubRepo}/releases/tag/v${version}. You can install the universal APK. If you want to install the application from the app bundle, you can follow instructions [here](https://github.com/${gitHubRepo}/blob/develop/docs/install_from_github_release.md). Please report any feedback. Thanks!"
printf "%s\n\n" "${message}"

if [[ -z "${releaseBotToken}" || -z "${releaseRoomId}" || -z "${releaseHomeserver}" ]]; then
  read -r -p "SEVENTWOS_RELEASE_MATRIX_TOKEN, SEVENTWOS_RELEASE_MATRIX_ROOM_ID and SEVENTWOS_RELEASE_MATRIX_HOMESERVER are not all defined in the environment. Cannot send the message for you. Please send it manually, and press enter to continue. "
else
  read -r -p "Send this message to the room (yes/no) default to yes? " doSend
  doSend=${doSend:-yes}
  if [ "${doSend}" == "yes" ]; then
    printf "Sending message...\n"
    transactionId=$(openssl rand -hex 16)
    curl -X PUT --data "{\"msgtype\":\"m.text\",\"body\":\"${message}\"}" -H "Authorization: Bearer ${releaseBotToken}" "${releaseHomeserver}/_matrix/client/v3/rooms/${releaseRoomId}/send/m.room.message/\$local.${transactionId}"
  else
    printf "Message not sent, please send it manually!\n"
  fi
fi

printf "\n================================================================================\n"
printf "Congratulation! Kudos for using this script! Have a nice day!\n"
printf "================================================================================\n"
