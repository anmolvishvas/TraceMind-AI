# TraceMind AI — Frontend Dashboard

This directory contains the React 18 + TypeScript + Tailwind CSS web dashboard and telemetry visualization interface for **TraceMind AI**.

## Directory Layout

```
frontend/
├── public/              # Static assets and icons
├── src/
│   ├── main.tsx         # Application entry point
│   ├── App.tsx          # Master shell and route navigation
│   ├── index.css        # Tailwind directives and base styles
│   ├── components/      # Reusable UI components (MetricCards, LogViewer, Timeline)
│   ├── pages/           # Screen views (Overview, Incidents, LogExplorer, Anomaly)
│   └── services/        # API client and streaming endpoints
├── package.json         # Dependencies and scripts
├── tailwind.config.js   # Enterprise dark-mode design tokens
├── tsconfig.json        # Strict TypeScript compiler options
└── vite.config.ts       # Vite bundling and dev server configuration
```

## Local Development

```bash
# Install dependencies
npm install

# Start Vite development server
npm run dev

# Run TypeScript type check
npm run typecheck

# Run unit tests
npm run test:run

# Build production bundle
npm run build
```
