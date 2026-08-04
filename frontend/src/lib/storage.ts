export interface StorageCodec<T> {
  serialize(value: T): string;
  deserialize(value: string): T;
}

export function createJsonStorageCodec<T>(): StorageCodec<T> {
  return {
    serialize: (value) => JSON.stringify(value),
    deserialize: (value) => JSON.parse(value) as T,
  };
}

export function readLocalStorage<T>(
  key: string,
  fallback: T,
  codec: StorageCodec<T>,
): T {
  if (typeof window === "undefined") {
    return fallback;
  }

  const storedValue = window.localStorage.getItem(key);

  if (storedValue === null) {
    return fallback;
  }

  try {
    return codec.deserialize(storedValue);
  } catch {
    return fallback;
  }
}

export function writeLocalStorage<T>(
  key: string,
  value: T,
  codec: StorageCodec<T>,
) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(key, codec.serialize(value));
}

export function removeLocalStorage(key: string) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(key);
}
