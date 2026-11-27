import { generateColors } from '@mantine/colors-generator';
import { Button, createTheme } from '@mantine/core';

export const theme = createTheme({
    colors: { brand: generateColors('#4F5BD5') },
    primaryColor: 'brand',
    black: '#22262E',
    fontFamily: "'Inter Variable', system-ui, sans-serif",
    headings: { fontFamily: "'Inter Variable', system-ui, sans-serif" },
    defaultRadius: 'md',
    cursorType: 'pointer',
    components: {
        Button: Button.extend({
            styles: { root: { cursor: 'pointer' } },
        }),
    },
});
