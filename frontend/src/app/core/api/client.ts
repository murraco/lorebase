import createClient from 'openapi-fetch';

import { readCookie } from './cookies';
import type { paths } from './schema';

// Paths in the generated schema already include the `/api` prefix, and an
// empty baseUrl keeps requests same-origin — the CSRF cookie Django sets
// only gets sent back automatically when the request is same-origin.
export const apiClient = createClient<paths>({ baseUrl: '' });

apiClient.use({
  onRequest({ request }) {
    const token = readCookie('csrftoken');
    if (token) {
      request.headers.set('X-CSRFToken', token);
    }
    return request;
  },
});
