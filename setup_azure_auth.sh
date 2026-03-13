#!/bin/bash

# Azure App Registration Setup Script for SharePoint MCP Server
# Automates the creation of an App Registration, Client Secret, and Permissions.

set -e

# --- Configuration ---
GRAPH_RESOURCE_APP_ID="00000003-0000-0000-0000-c00000000000"
# Permission UUIDs (Application Scope)
PERM_SITES_READ_ALL="62a82d76-d045-4ceb-92ea-1f211dec6936"
PERM_SITES_SELECTED="204e0828-b5ca-4ad8-b9f3-f32a958e7cc4"

# --- Functions ---
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- Check Prerequisites ---
if ! command_exists az; then
    echo "❌ Azure CLI ('az') is not installed. Please install it first:"
    echo "   brew install azure-cli (macOS)"
    echo "   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash (Linux)"
    exit 1
fi

echo "Welcome to the SharePoint MCP Auth Setup Wizard!"
echo "This script will create an Azure AD App Registration for you."
echo ""

# --- Check Login ---
echo "Checking Azure login status..."
ACCOUNT=$(az account show --query "user.name" -o tsv 2>/dev/null || echo "")
if [ -z "$ACCOUNT" ]; then
    echo "⚠️  You are not logged in. Opening login window..."
    az login >/dev/null
    ACCOUNT=$(az account show --query "user.name" -o tsv)
fi
TENANT_ID=$(az account show --query "tenantId" -o tsv)
echo "✅ Logged in as: $ACCOUNT (Tenant: $TENANT_ID)"
echo ""

# --- Get App Name ---
read -p "Enter a name for the App Registration [SharePoint-List-MCP-Search]: " APP_NAME
APP_NAME=${APP_NAME:-SharePoint-List-MCP-Search}

# --- Create App Registration ---
echo "Creating App Registration '$APP_NAME'..."
APP_ID=$(az ad app create --display-name "$APP_NAME" --query "appId" -o tsv)
echo "✅ App Created. Client ID: $APP_ID"

# --- Create Service Principal ---
# Required to grant permissions
echo "Creating Service Principal..."
SP_ID=$(az ad sp create --id "$APP_ID" --query "id" -o tsv)
echo "✅ Service Principal Created."

# --- Create Client Secret ---
echo "Generating Client Secret..."
# Reset creates a new one. Append ensures we don't wipe existing if running again (though this is new app).
CLIENT_SECRET=$(az ad app credential reset --id "$APP_ID" --append --display-name "MCP Server Secret" --years 1 --query "password" -o tsv)
echo "✅ Client Secret Generated."

# --- Select Permission ---
echo ""
echo "Select API Permission Level:"
echo "1) Sites.Read.All (Easy, grants read access to ALL sites)"
echo "2) Sites.Selected (Secure, grants access only to specific sites you authorize later)"
read -p "Enter choice [2]: " PERM_CHOICE
PERM_CHOICE=${PERM_CHOICE:-2}

if [ "$PERM_CHOICE" == "1" ]; then
    PERM_ID="$PERM_SITES_READ_ALL"
    PERM_NAME="Sites.Read.All"
else
    PERM_ID="$PERM_SITES_SELECTED"
    PERM_NAME="Sites.Selected"
fi

# --- Add Permission ---
echo "Adding '$PERM_NAME' permission..."
az ad app permission add --id "$APP_ID" --api "$GRAPH_RESOURCE_APP_ID" --api-permissions "$PERM_ID=Role" >/dev/null
# Grant admin consent (if user has rights)
echo "Attempting to grant Admin Consent..."
if az ad app permission admin-consent --id "$APP_ID" 2>/dev/null; then
    echo "✅ Admin Consent Granted successfully."
else
    echo "⚠️  Could not grant Admin Consent automatically (you might not be a Global Admin)."
    echo "   👉 Please go to the Azure Portal > App Registrations > $APP_NAME > API Permissions"
    echo "   👉 Click 'Grant admin consent for [Your Org]'"
fi

# --- Output .env ---
echo ""
echo "🎉 Setup Complete!"
echo ""
echo "Copy the following into your .env file:"
echo "---------------------------------------------------"
echo "TENANT_ID=$TENANT_ID"
echo "CLIENT_ID=$APP_ID"
echo "CLIENT_SECRET=$CLIENT_SECRET"
echo "---------------------------------------------------"
echo ""
if [ "$PERM_CHOICE" == "2" ]; then
    echo "NOTE: You chose 'Sites.Selected'. The bot currently has NO access."
    echo "You must now explicitly grant access to specific sites using the Site ID."
    echo "Refer to the README 'Step 4' for the API call to do this."
fi
