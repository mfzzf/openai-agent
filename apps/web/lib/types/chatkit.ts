export type CreateSessionRequest = {
  userId?: string;
};

export type CreateSessionResponse = {
  clientSecret: string;
  expiresAt: number;
  workflowId: string;
};
