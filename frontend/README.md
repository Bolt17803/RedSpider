# RedSpider Frontend

A modern Next.js frontend for the RedSpider AI Agent Workflow System.

## Features

- 🎨 Minimalist modern design with matt finish and cyberpunk theme
- 🔄 Real-time workflow graph visualization showing active agent nodes
- 💬 Streaming chat interface
- 🌊 Server-Sent Events (SSE) for real-time updates

## Getting Started

1. Install dependencies:
```bash
npm install
```

2. Set up environment variables:
Create a `.env.local` file:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

3. Run the development server:
```bash
npm run dev
```

4. Open [http://localhost:3000](http://localhost:3000) in your browser

## Tech Stack

- Next.js 14
- TypeScript
- Tailwind CSS
- React

## Backend Integration

The frontend connects to the FastAPI backend running on `http://localhost:8000` by default. Make sure your backend is running before starting the frontend.

