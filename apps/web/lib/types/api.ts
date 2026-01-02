export type ApiError = {
  ok: false;
  error: {
    code: string;
    message: string;
  };
};
