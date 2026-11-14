#!/bin/sh
# build.sh: Groq Queen AI Studio (Mantra).app (shown as Groq/Queen AI Studio (Mantra)) + axread inside it. swiftc straight, no Xcode. Run ONLY by GitHub
# (.github/workflows/build.yml, SIGN=- NO_INSTALL=1): nothing is compiled on Marko's Mac (MANTRA_MANIFEST android-app.md §0).
# On the Mac the release zip is downloaded, unpacked into /Applications and signed "Mantra Apps" (install.sh).
set -e
cd "$(dirname "$0")"
V=$(sed -n 's/^let VERSION = \([0-9]*\)/\1/p' app/App.swift)
NAME="Groq Queen AI Studio (Mantra)"
DISPLAY="Groq/Queen AI Studio (Mantra)"
APP="build/$NAME.app"
rm -rf "$APP"; mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -swift-version 5 -parse-as-library -o "$APP/Contents/MacOS/GroqAIStudio" app/*.swift
swiftc -O -swift-version 5 -o "$APP/Contents/MacOS/axread" axread/main.swift
[ -x "$APP/Contents/MacOS/GroqAIStudio" ] && [ -x "$APP/Contents/MacOS/axread" ] || { echo "the app did not build"; exit 1; }
cat > "$APP/Contents/Info.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>$DISPLAY</string>
<key>CFBundleDisplayName</key><string>$DISPLAY</string>
<key>CFBundleIdentifier</key><string>community.auroville.groqaistudio</string>
<key>CFBundleExecutable</key><string>GroqAIStudio</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>$V</string>
<key>CFBundleVersion</key><string>$V</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PL
[ -f icon/AppIcon.icns ] && cp icon/AppIcon.icns "$APP/Contents/Resources/" && /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string AppIcon" "$APP/Contents/Info.plist" || true
codesign --force -s "${SIGN:-Mantra Apps}" "$APP/Contents/MacOS/axread"
codesign --force -s "${SIGN:-Mantra Apps}" "$APP"
echo "built $APP (v$V)"
