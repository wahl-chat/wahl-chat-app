type TruthyKinda = 'true' | 'false';

declare global {
  namespace NodeJS {
    interface ProcessEnv {
      SITE_URL: string;
      NEXT_PUBLIC_API_URL: string;
      NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY: string;
      NEXT_PUBLIC_FIREBASE_API_KEY: string;
      NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN: string;
      NEXT_PUBLIC_FIREBASE_PROJECT_ID: string;
      NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET: string;
      NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID: string;
      NEXT_PUBLIC_FIREBASE_APP_ID: string;
      NEXT_PUBLIC_STREAMING_MESSAGE_TIMEOUT_MS?: string;
      FIREBASE_PRIVATE_KEY: string;
      FIREBASE_CLIENT_EMAIL: string;
      STRIPE_SECRET_KEY: string;
      BUDGET_SPENT: TruthyKinda;
      REVALIDATE_SECRET: string;
      IS_EMBEDDED: TruthyKinda;
    }
  }
}
