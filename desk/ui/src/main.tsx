import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import '@fontsource/source-sans-3/latin-400.css';
import '@fontsource/source-sans-3/latin-500.css';
import '@fontsource/source-sans-3/latin-600.css';
import '@fontsource/source-sans-3/greek-400.css';
import '@fontsource/source-sans-3/greek-600.css';
import '@fontsource/source-serif-4/latin-400.css';
import '@fontsource/source-serif-4/latin-600.css';
import './styles/tokens.css';
import './styles/base.css';
import App from './App';
import { SnapshotProvider } from './state/SnapshotContext';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <SnapshotProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </SnapshotProvider>
  </React.StrictMode>,
);
