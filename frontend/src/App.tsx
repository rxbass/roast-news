import { createBrowserRouter, RouterProvider } from 'react-router-dom';

import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';
import { HomePage } from './pages/HomePage';
import { NotFoundPage } from './pages/NotFoundPage';

// Home stays in the main bundle (it's the landing page); the rest load on demand.
const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      {
        path: '/roast/:id',
        lazy: async () => ({ Component: (await import('./pages/RoastPage')).RoastPage }),
      },
      {
        path: '/my-roasts',
        lazy: async () => {
          const { MyRoastsPage } = await import('./pages/MyRoastsPage');
          return {
            element: (
              <ProtectedRoute>
                <MyRoastsPage />
              </ProtectedRoute>
            ),
          };
        },
      },
      {
        path: '/auth/callback',
        lazy: async () => ({ Component: (await import('./pages/AuthCallbackPage')).AuthCallbackPage }),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
