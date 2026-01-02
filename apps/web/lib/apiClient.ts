export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body ?? {}),
  });

  const data = (await response.json()) as T & {
    ok?: boolean;
    error?: { message?: string };
  };

  if (!response.ok || data.ok === false) {
    const message = data.error?.message ?? "Request failed";
    throw new Error(message);
  }

  return data;
}

export async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  const data = (await response.json()) as T & {
    ok?: boolean;
    error?: { message?: string };
  };

  if (!response.ok || data.ok === false) {
    const message = data.error?.message ?? "Request failed";
    throw new Error(message);
  }

  return data;
}
