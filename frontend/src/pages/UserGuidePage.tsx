import React from 'react';
import { BookOpen, Monitor, Terminal, FileCode, CheckCircle, ShieldAlert } from 'lucide-react';

export default function UserGuidePage() {
  return (
    <div className="p-8 max-w-5xl mx-auto h-full overflow-y-auto">
      <div className="flex items-center gap-3 mb-8">
        <BookOpen className="w-10 h-10 text-blue-500" />
        <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-600">
          StreamPulse Real-Time Telemetry - User Guide
        </h1>
      </div>

      <p className="text-lg text-gray-300 mb-8 leading-relaxed">
        StreamPulse ingests, processes, and visualizes high-throughput streaming data and telemetry events from across the ecosystem.
      </p>

      <div className="space-y-8 text-gray-200">
        
        {/* Core Features Section */}
        <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
            <Monitor className="w-6 h-6 text-green-400" /> Interface & Features Walkthrough
          </h2>
          <div className="space-y-4">
            
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-blue-400 text-lg mb-2">1. Webhook Integrations (HMAC)</h3>
              <p className="text-sm text-gray-300">Securely receive high-throughput streaming events via `/webhook`. All incoming payloads are verified using SHA-256 HMAC signatures.</p>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-purple-400 text-lg mb-2">2. n8n Workflow Automation</h3>
              <p className="text-sm text-gray-300">StreamPulse seamlessly integrates with its internal n8n service to trigger complex automations when specific telemetry patterns are detected.</p>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-amber-400 text-lg mb-2">3. Live Feed Dashboard</h3>
              <p className="text-sm text-gray-300">Watch incoming telemetry events as they hit the database in real-time, visualized via server-sent events (SSE).</p>
            </div>
          </div>
        </section>

        {/* Integration Setup Section */}
        <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
            <Terminal className="w-6 h-6 text-orange-400" /> Integration & Setup Instructions
          </h2>
          
            <div>
              <h3 className="font-semibold text-lg text-gray-100 flex items-center gap-2 mb-2">
                <FileCode className="w-5 h-5 text-gray-400" /> Environment Setup
              </h3>
              <p className="text-sm text-gray-300 mb-3">To run StreamPulse locally, ensure the following environment variables are set in your <code>.env</code> file:</p>
              <ul className="list-disc list-inside text-sm font-mono text-green-300 space-y-2 ml-2 bg-gray-950 p-4 rounded-lg">
                <li><code>PULSE_DB_PATH</code></li>\n<li><code>KAFKA_BROKER_URL</code></li>
              </ul>
              <p className="text-sm text-gray-300 mt-4">Once configured, start the backend services using <code>docker-compose</code> or the respective python runner script before accessing this frontend.</p>
            </div>
        </section>

        {/* Security & Best Practices */}
        <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
            <ShieldAlert className="w-6 h-6 text-red-400" /> Security & Best Practices
          </h2>
          <ul className="space-y-3">
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-green-400 shrink-0 mt-0.5" />
              <span className="text-sm text-gray-300">Always use a virtual environment (`.venv`) when running python backends to isolate dependencies.</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-green-400 shrink-0 mt-0.5" />
              <span className="text-sm text-gray-300">Never commit your `.env` files or hardcode API keys. The system uses secure environment variables for all external integrations.</span>
            </li>
          </ul>
        </section>

      </div>
    </div>
  );
}
