import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        // Las gráficas y la rejilla pesan más que todo el código propio: cada una va
        // en su trozo para que solo se descarguen al abrir una pantalla que las use.
        codeSplitting: {
          groups: [
            { name: 'echarts', test: /node_modules[\\/](echarts|zrender)[\\/]/ },
            { name: 'ag-grid', test: /node_modules[\\/]ag-grid-community[\\/]/ },
          ],
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:5070',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: 'src/setupTests.ts',
  },
});
