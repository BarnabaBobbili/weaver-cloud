# Weaver Frontend

Frontend for Weaver, built with React + TypeScript + Vite.

## Features

- Role-aware navigation (`admin`, `analyst`, `viewer`)
- Auth and MFA flows
- Classification, encryption/decryption, sharing, analytics pages
- Admin pages for users, policies, shares, and compliance

## Development

```powershell
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver\frontend"
npm install
npm run dev
```

Dev URL: `http://localhost:5173`

## Production Build

```powershell
npm run build
npm run preview
```

## Environment

- `VITE_API_URL` -> backend base URL used by client API calls.

Example:

```powershell
$env:VITE_API_URL="https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io"
npm run build
```

## Deployment Target

- Azure Static Web Apps
- Current hostname: `https://salmon-meadow-04fa55300.1.azurestaticapps.net`
