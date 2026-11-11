import { afterEach } from 'vitest';
import { cleanup, configure } from '@testing-library/react';

// AG Grid y ECharts tardan en montar en jsdom: con la CPU ocupada el 1 s por defecto de
// waitFor/findBy* daba un fallo intermitente (1 de 11 corridas) en MarketScreen.
configure({ asyncUtilTimeout: 5000 });

afterEach(() => cleanup());
