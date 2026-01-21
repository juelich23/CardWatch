import { ApolloClient, InMemoryCache, HttpLink, ApolloLink } from '@apollo/client';

const CACHE_KEY = 'apollo-cache-persist';
const CACHE_VERSION_KEY = 'apollo-cache-version';
const CURRENT_CACHE_VERSION = '2'; // Increment to invalidate old cache

// Restore cache from localStorage asynchronously to avoid blocking initial render
const restoreCacheAsync = (cache: InMemoryCache): Promise<void> => {
  return new Promise((resolve) => {
    if (typeof window === 'undefined') {
      resolve();
      return;
    }

    // Check cache version - clear if outdated
    const storedVersion = localStorage.getItem(CACHE_VERSION_KEY);
    if (storedVersion !== CURRENT_CACHE_VERSION) {
      localStorage.removeItem(CACHE_KEY);
      localStorage.setItem(CACHE_VERSION_KEY, CURRENT_CACHE_VERSION);
      resolve();
      return;
    }

    // Use requestIdleCallback to restore cache during idle time
    const restore = () => {
      try {
        const cached = localStorage.getItem(CACHE_KEY);
        if (cached) {
          const data = JSON.parse(cached);
          cache.restore(data);
        }
      } catch (e) {
        console.warn('Failed to restore Apollo cache:', e);
      }
      resolve();
    };

    if ('requestIdleCallback' in window) {
      (window as Window & { requestIdleCallback: (cb: () => void) => void }).requestIdleCallback(restore);
    } else {
      // Fallback for Safari - use setTimeout with 0 delay
      setTimeout(restore, 0);
    }
  });
};

// Persist cache to localStorage (debounced)
let persistTimeout: ReturnType<typeof setTimeout> | null = null;
const persistCache = (cache: InMemoryCache) => {
  if (typeof window === 'undefined') return;

  if (persistTimeout) clearTimeout(persistTimeout);
  persistTimeout = setTimeout(() => {
    try {
      const data = cache.extract();
      localStorage.setItem(CACHE_KEY, JSON.stringify(data));
    } catch (e) {
      console.warn('Failed to persist Apollo cache:', e);
    }
  }, 1000); // Debounce by 1 second
};

const createApolloClient = () => {
  const cache = new InMemoryCache({
    typePolicies: {
      Query: {
        fields: {
          // Each unique combination of args gets its own cache entry
          auctionItems: {
            keyArgs: ['status', 'page', 'pageSize'],
            merge(existing, incoming) {
              return incoming; // Replace cache with fresh data
            },
          },
        },
      },
    },
  });

  // HTTP link for making requests
  const httpLink = new HttpLink({
    uri: process.env.NEXT_PUBLIC_GRAPHQL_URL || 'https://cardwatch-api-production.up.railway.app/graphql',
    credentials: 'include',
  });

  // Auth link to add JWT token to requests
  const authLink = new ApolloLink((operation, forward) => {
    // Get the authentication token from local storage if it exists
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;

    // Debug: log token status for mutations
    if (typeof window !== 'undefined' && operation.operationName) {
      console.log(`[GraphQL] ${operation.operationName} - Token: ${token ? 'present' : 'missing'}`);
    }

    // Add the authorization header
    operation.setContext(({ headers = {} }) => ({
      headers: {
        ...headers,
        authorization: token ? `Bearer ${token}` : '',
      },
    }));

    return forward(operation);
  });

  const client = new ApolloClient({
    link: ApolloLink.from([authLink, httpLink]),
    cache,
    defaultOptions: {
      watchQuery: {
        fetchPolicy: 'cache-first', // Show cached data instantly
        nextFetchPolicy: 'cache-and-network', // Then refresh in background
      },
      query: {
        fetchPolicy: 'cache-first',
      },
    },
  });

  // Restore cache asynchronously during idle time (non-blocking)
  if (typeof window !== 'undefined') {
    restoreCacheAsync(cache);

    // Persist cache on every write (debounced)
    const originalWrite = cache.write.bind(cache);
    cache.write = (...args) => {
      const result = originalWrite(...args);
      persistCache(cache);
      return result;
    };
  }

  return client;
};

export default createApolloClient;
