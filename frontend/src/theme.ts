import { extendTheme, type StyleFunctionProps, type ThemeConfig } from '@chakra-ui/react';

const config: ThemeConfig = {
  initialColorMode: 'light',
  useSystemColorMode: false,
};

/** Spicy chili palette: orange (brand) to red (chili), with a turmeric accent. */
const colors = {
  brand: {
    50: '#fff4ec',
    100: '#ffe1cc',
    200: '#ffc099',
    300: '#ff9a5c',
    400: '#ff7a2e',
    500: '#f45b0f',
    600: '#d9420a',
    700: '#b3300b',
    800: '#8c2510',
    900: '#6b1d10',
  },
  chili: {
    50: '#fff1f1',
    100: '#ffdcdc',
    200: '#ffb3b3',
    300: '#ff7f7f',
    400: '#f74b4b',
    500: '#e52222',
    600: '#c41616',
    700: '#a01414',
    800: '#7f1616',
    900: '#621414',
  },
  turmeric: {
    50: '#fffbea',
    100: '#fff3c4',
    200: '#ffe78a',
    300: '#ffd54f',
    400: '#ffc21f',
    500: '#f5a400',
    600: '#d17f00',
    700: '#a65d02',
    800: '#874809',
    900: '#6f3b0c',
  },
};

const fonts = {
  heading: `'Bungee', system-ui, sans-serif`,
  body: `'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`,
};

const theme = extendTheme({
  config,
  colors,
  fonts,
  styles: {
    global: (props: StyleFunctionProps) => ({
      body: {
        bg: props.colorMode === 'dark' ? 'gray.900' : 'orange.50',
        color: props.colorMode === 'dark' ? 'gray.100' : 'gray.800',
      },
    }),
  },
  components: {
    Button: {
      defaultProps: { colorScheme: 'brand' },
      baseStyle: { borderRadius: 'full', fontWeight: 'semibold' },
    },
    Heading: {
      baseStyle: { letterSpacing: 'wide' },
    },
  },
});

export default theme;
