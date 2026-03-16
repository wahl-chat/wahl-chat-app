/**
 * Case Conversion Utilities
 * Convert between camelCase (frontend) and snake_case (backend)
 */

type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

/**
 * Convert a string from snake_case to camelCase
 */
function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

/**
 * Convert a string from camelCase to snake_case
 */
function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

/**
 * Recursively convert all object keys from snake_case to camelCase
 */
export function keysToCamelCase<T>(obj: unknown): T {
  if (obj === null || obj === undefined) {
    return obj as T;
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => keysToCamelCase(item)) as T;
  }

  if (typeof obj === 'object') {
    const result: Record<string, JsonValue> = {};
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      const camelKey = snakeToCamel(key);
      result[camelKey] = keysToCamelCase(value) as JsonValue;
    }
    return result as T;
  }

  return obj as T;
}

/**
 * Recursively convert all object keys from camelCase to snake_case
 */
export function keysToSnakeCase<T>(obj: unknown): T {
  if (obj === null || obj === undefined) {
    return obj as T;
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => keysToSnakeCase(item)) as T;
  }

  if (typeof obj === 'object') {
    const result: Record<string, JsonValue> = {};
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      const snakeKey = camelToSnake(key);
      result[snakeKey] = keysToSnakeCase(value) as JsonValue;
    }
    return result as T;
  }

  return obj as T;
}
