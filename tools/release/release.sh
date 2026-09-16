#!/usr/bin/env bash

# Copyright (c) 2025 Element Creations Ltd.
# Copyright 2023-2024 New Vector Ltd.
#
# SPDX-License-Identifier: AGPL-3.0-only.
# Please see LICENSE files in the repository root for full details.

# do not exit when any command fails (issue with git flow)
set +e

gitHubRepo="seventwos-app/usr-workspace-android"
applicationId="org.seventwos.workspace"
productName="Seventwos Workspace for Android"

printf "\n================================================================================\n"
printf "|                    Welcome to the release script!                            |\n"
printf "================================================================================\n"

printf "Checking environment...\n"
envError=0

# Check that bundletool is installed
if ! command -v bundletool &> /dev/null
then
    printf "Fatal: bundletool is not installed. You can install it running \`brew install bundletool\`\n"
    envError=1
fi

# GitHub token
gitHubToken="${SEVENTWOS_GITHUB_TOKEN}"
if [[ -z "${gitHubToken}" ]]; then
    printf "Fatal: SEVENTWOS_GITHUB_TOKEN is not defined in the environment.\n"
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

# Read minSdkVersion from file plugins/src/main/kotlin/Versions.kt
minSdkVersion=$(grep "MIN_SDK_FOSS =" ./plugins/src/main/kotlin/Versions.kt |cut -d '=' -f 2 |xargs)
# Read buildToolsVersion from file plugins/src/main/kotlin/Versions.kt
buildToolsVersion=$(grep "BUILD_TOOLS_VERSION =" ./plugins/src/main/kotlin/Versions.kt |cut -d '=' -f 2 |xargs)
buildToolsPath="${androidHome}/build-tools/${buildToolsVersion}"

if [[ ! -d ${buildToolsPath} ]]; then
    printf "Fatal: %s folder not found, ensure that you have installed the SDK version %s.\n" "${buildToolsPath}" "${buildToolsVersion}"
    exit 1
fi

# Check if git flow is enabled
gitFlowDevelop=$(git config gitflow.branch.develop)
if [[ ${gitFlowDevelop} != "" ]]
then
    printf "Git flow is initialized\n"
else
    printf "Git flow is not initialized. Initializing...\n"
    ./tools/gitflow/gitflow-init.sh
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
git flow release start "${version}"

# Note: in case the release is already started and the script is started again, checkout the release branch again.
ret=$?
if [[ $ret -ne 0 ]]; then
  printf "Mmh, it seems that the release is already started. I'm displaying the changes now:\n"
  git diff --stat "release/${version}" origin/main
  printf "Do you want to continue the release using its contents?\n\n"
  read -r -p "Continue (yes/no) default to yes? " doContinue
  doContinue=${doContinue:-yes}
  if [ "${doContinue}" == "no" ]; then
    printf "OK, exiting, you can start the release again with the command 'git flow release start %s'\n" "${version}"
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
git flow release finish "${version}"

printf "\n================================================================================\n"
read -r -p "Done, push the branch 'main' and the new tag (yes/no) default to yes? " doPush
doPush=${doPush:-yes}

if [ "${doPush}" == "yes" ]; then
  printf "Pushing branch 'main' and tag 'v%s'...\n" "${version}"
  git push origin main
  git push origin "v${version}"
else
    printf "Not pushing, do not forget to push manually!\n"
fi

printf "\n================================================================================\n"
printf "Checking out develop...\n"
git checkout develop

printf "\n================================================================================\n"
printf "The workflow 'Build signed Android release artifacts' (release.yml) is manually dispatched and only runs on the 'develop' branch.\n"
printf "Please push 'develop', then start a run from https://github.com/%s/actions/workflows/release.yml (\"Run workflow\" on the 'develop' branch).\n" "${gitHubRepo}"
read -r -p "Please enter the url of the run, no need to wait for it to complete (example: https://github.com/${gitHubRepo}/actions/runs/9065756777): " runUrl

targetPath="./tmp/seventwos-workspace/${version}"

printf "\n================================================================================\n"
printf "Downloading the artifacts...\n"

ret=1

while [[ $ret -ne 0 ]]; do
  python3 ./tools/github/download_all_github_artifacts.py \
     --token "${gitHubToken}" \
     --runUrl "${runUrl}" \
     --directory "${targetPath}"

  ret=$?
  if [[ $ret -ne 0 ]]; then
    read -r -p "Error while downloading the artifacts. You may want to fix the issue and retry. Retry (yes/no) default to yes? " doRetry
    doRetry=${doRetry:-yes}
    if [ "${doRetry}" == "no" ]; then
      exit 1
    fi
  fi
done

printf "\n================================================================================\n"
printf "Unzipping the release artifact...\n"

# The workflow uploads a single artifact named `seventwos-workspace-android-<commit sha>`, containing
# both the Gplay app bundle and the F-Droid APKs, already signed with the release key.
artifactZip=$(find "${targetPath}" -maxdepth 1 -name 'seventwos-workspace-android-*.zip' | head -n 1)
if [[ -z "${artifactZip}" ]]; then
  printf "Fatal: no artifact matching 'seventwos-workspace-android-*.zip' found in %s.\n" "${targetPath}"
  exit 1
fi

artifactPath="${targetPath}/artifact"
unzip -o "${artifactZip}" -d "${artifactPath}"

# Paths inside the artifact, relative to the `app/build/outputs` folder uploaded by the workflow.
fdroidTargetPath="${artifactPath}/apk/fdroid/release"
gplayTargetPath="${artifactPath}/bundle/gplayRelease"
signedBundlePath="${gplayTargetPath}/app-gplay-release.aab"

printf "\n================================================================================\n"
printf "Verifying the F-Droid APKs...\n"

for apkFile in "${fdroidTargetPath}"/*.apk; do
  printf "File %s:\n" "$(basename "${apkFile}")"
  "${buildToolsPath}"/apksigner verify --min-sdk-version "${minSdkVersion}" --verbose --print-certs "${apkFile}" \
    | tee "${targetPath}"/apksigner.txt
  if grep -qi "Android Debug" "${targetPath}"/apksigner.txt; then
    printf "Fatal: %s is signed with the Android debug certificate.\n" "${apkFile}"
    exit 1
  fi
  "${buildToolsPath}"/aapt dump badging "${apkFile}" | grep -F "package: name='${applicationId}'"
done
rm -f "${targetPath}"/apksigner.txt

printf "\n"
read -r -p "Does it look correct? Press enter when it's done. "

printf "\n================================================================================\n"
printf "The APKs in %s are signed and verified!\n" "${fdroidTargetPath}"

printf "\n================================================================================\n"
printf "Verifying the Gplay app bundle %s...\n" "${signedBundlePath}"

jarsigner -verify "${signedBundlePath}"

printf "Please check the information below:\n"

printf "Version code: "
bundletool dump manifest --bundle="${signedBundlePath}" --xpath=/manifest/@android:versionCode
printf "Version name: "
bundletool dump manifest --bundle="${signedBundlePath}" --xpath=/manifest/@android:versionName

printf "\n"
read -r -p "Does it look correct? Press enter to continue. "

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
printf " - download the universal APK, to be able to provide it to the GitHub release: click on the right arrow next to the \"App bundle\", then click on the \"Download\" tab, and download the \"Signed, universal APK\".\n"
printf " - submit the release.\n"
read -r -p "Press enter to continue. "

printf "You can then go to \"Publishing overview\" and send the new release for a review by Google.\n"
read -r -p "Press enter to continue. "

printf "\n================================================================================\n"
githubCreateReleaseLink="https://github.com/${gitHubRepo}/releases/new?tag=v${version}&title=Seventwos%20Workspace%20for%20Android%20v${version}"
printf "Creating the release on gitHub.\n"
printf -- "Open this link: %s\n" "${githubCreateReleaseLink}"
printf "Then\n"
printf " - Click on the 'Generate releases notes' button.\n"
printf " - Optionally reorder items and fix typos.\n"
printf " - Add the file %s to the GitHub release.\n" "${signedBundlePath}"
printf " - Add the universal APK, downloaded from the GooglePlay console to the GitHub release.\n"
printf " - Add the 4 signed APKs for F-Droid, located at %s to the GitHub release.\n" "${fdroidTargetPath}"
read -r -p ". Press enter to continue. "

printf "\n================================================================================\n"
printf "Update the project release notes:\n\n"

read -r -p "Copy the content of the release note generated by GitHub to the file CHANGES.md and press enter to commit the change. "

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
