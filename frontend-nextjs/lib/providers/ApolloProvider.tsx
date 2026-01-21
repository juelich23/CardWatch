'use client';

import { ApolloProvider as ApolloProviderBase } from '@apollo/client/react';
import createApolloClient from '../graphql/client';
import { ReactNode } from 'react';

const client = createApolloClient();

export function ApolloProvider({ children }: { children: ReactNode }) {
  return <ApolloProviderBase client={client}>{children}</ApolloProviderBase>;
}
