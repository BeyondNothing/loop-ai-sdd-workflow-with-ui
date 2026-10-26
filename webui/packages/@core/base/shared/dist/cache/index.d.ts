interface IStorageDriver {
  clear(): Promise<void>;
  getItem<T>(key: string): Promise<null | T>;
  keys(): Promise<string[]>;
  removeItem(key: string): Promise<void>;
  setItem(key: string, value: unknown): Promise<void>;
}
interface StorageItem<T> {
  expiry?: number;
  value: T;
}
interface StorageManagerOptions {
  driver?: IStorageDriver;
  prefix?: string;
}
interface IndexedDBDriverOptions {
  dbName?: string;
  dbVersion?: number;
  storeName?: string;
}
declare class IndexedDBDriver implements IStorageDriver {
  private dbName;
  private dbPromise;
  private dbVersion;
  private storeName;
  constructor({ dbName, dbVersion, storeName }?: IndexedDBDriverOptions);
  clear(): Promise<void>;
  getItem<T>(key: string): Promise<null | T>;
  keys(): Promise<string[]>;
  removeItem(key: string): Promise<void>;
  setItem(key: string, value: unknown): Promise<void>;
  private getDB;
  private openDB;
}
type StorageType = 'localStorage' | 'sessionStorage';
interface LocalStorageDriverOptions {
  storageType?: StorageType;
}
declare class LocalStorageDriver implements IStorageDriver {
  private storage;
  constructor({ storageType }?: LocalStorageDriverOptions);
  clear(): Promise<void>;
  getItem<T>(key: string): Promise<null | T>;
  keys(): Promise<string[]>;
  removeItem(key: string): Promise<void>;
  setItem(key: string, value: unknown): Promise<void>;
}
declare class MemoryStorageDriver implements IStorageDriver {
  private store;
  clear(): Promise<void>;
  getItem<T>(key: string): Promise<null | T>;
  keys(): Promise<string[]>;
  removeItem(key: string): Promise<void>;
  setItem(key: string, value: unknown): Promise<void>;
}
declare class StorageManager {
  private driver;
  private prefix;
  constructor({ driver, prefix }?: StorageManagerOptions);
  clear(): Promise<void>;
  clearExpiredItems(): Promise<void>;
  getItem<T>(key: string, defaultValue?: null | T): Promise<null | T>;
  keys(): Promise<string[]>;
  removeItem(key: string): Promise<void>;
  setItem(key: string, value: unknown, ttl?: number): Promise<void>;
  private createDefaultDriver;
  private getFullKey;
}
export { type IStorageDriver, IndexedDBDriver, type IndexedDBDriverOptions, LocalStorageDriver, type LocalStorageDriverOptions, MemoryStorageDriver, type StorageItem, StorageManager, type StorageManagerOptions };