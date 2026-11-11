import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
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
