#!/usr/bin/env bash

set -e

help ()
{
	echo -e "Usage: $0 VERSION"
	echo -e ""
	echo -e "\tVERSION\t\tNew version to create release"
}

new_version="$1"
if [ -z "$new_version" ]
then
	help
	exit 1
fi

echo -e "Updating CHANGELOG."
version_date="${new_version} - $(date +%F)"
version_string="${version_date}\n$(echo $version_date | sed -e 's|.|-|g')\n"
sed -i -e 9a"$version_string" CHANGELOG

echo -e "Creating commit and tag:"
changes=$(tail -n +13 CHANGELOG | sed -e "/-----/,999999d" | head -n -1)
echo -e "Release $new_version"
echo -e "$changes"

# commit CHANGELOG
git add CHANGELOG
git commit --gpg-sign --message "Release $new_version" --message "$changes"

# create signed tag
git tag --annotate --sign "$new_version" \
        --message="Release $new_version" \
        --message="$changes"

echo -e "\n\nReady to 'git push'."
