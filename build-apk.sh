#!/bin/bash

# BlueCord APK Builder Script
# Compile facilement l'APK Android

set -e

echo "╔════════════════════════════════════════╗"
echo "║     BlueCord APK Builder v2.7.4        ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Menu
echo "Choisissez une méthode de build:"
echo ""
echo "1) Build Cloud (Expo - Recommandé)"
echo "2) Build Local (Nécessite Android SDK)"
echo "3) Quick Dev Build"
echo "4) Quitter"
echo ""
read -p "Sélectionnez (1-4): " choice

case $choice in
  1)
    echo -e "${YELLOW}Building with Expo Cloud...${NC}"
    cd mobile

    # Check if eas-cli is installed
    if ! command -v eas &> /dev/null; then
      echo -e "${YELLOW}Installing eas-cli...${NC}"
      npm install -g eas-cli
    fi

    echo "Installing dependencies..."
    npm install

    echo "Logging into Expo..."
    npx eas-cli login

    echo "Configuring build..."
    npx eas-cli build:configure --platform android

    echo -e "${YELLOW}Starting Expo Cloud build...${NC}"
    npx eas-cli build --platform android

    echo -e "${GREEN}✓ Build complete! Check your Expo dashboard for the APK.${NC}"
    ;;

  2)
    echo -e "${YELLOW}Building locally...${NC}"
    cd mobile

    # Check for Android SDK
    if [ ! -d "$ANDROID_SDK_ROOT" ] && [ ! -d "$ANDROID_HOME" ]; then
      echo -e "${RED}✗ Android SDK not found!${NC}"
      echo "Set ANDROID_SDK_ROOT or ANDROID_HOME environment variable"
      exit 1
    fi

    echo "Installing dependencies..."
    npm install

    echo -e "${YELLOW}Building APK...${NC}"
    npx eas-cli build --platform android --local

    echo -e "${GREEN}✓ Build complete!${NC}"
    echo "APK location: ./dist/"
    ;;

  3)
    echo -e "${YELLOW}Quick dev build...${NC}"
    cd mobile

    echo "Installing dependencies..."
    npm install

    echo "Starting dev server..."
    echo -e "${GREEN}✓ Run 'npm start' to start the Expo dev server${NC}"
    npm start
    ;;

  4)
    echo -e "${YELLOW}Exiting...${NC}"
    exit 0
    ;;

  *)
    echo -e "${RED}Invalid choice!${NC}"
    exit 1
    ;;
esac

echo ""
echo "╔════════════════════════════════════════╗"
echo "║         Build Process Complete         ║"
echo "╚════════════════════════════════════════╝"
