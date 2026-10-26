import { ConfigEnv, Plugin, PluginOption, UserConfig, UserConfigFnPromise } from "vite";
import { PluginVisualizerOptions, visualizer as viteVisualizerPlugin } from "rollup-plugin-visualizer";
import viteDtsPlugin from "unplugin-dts/vite";
import viteCompressPlugin from "vite-plugin-compression";
import { Options } from "vite-plugin-pwa";
import { Options as Options$1 } from "html-minifier-terser";
import { PluginOptions } from "unplugin-dts";
interface IImportMap {
  imports?: Record<string, string>;
  scopes?: {
    [scope: string]: Record<string, string>;
  };
}
interface PrintPluginOptions {
  infoMap?: Record<string, string | undefined>;
}
interface NitroMockPluginOptions {
  mockServerPackage?: string;
  port?: number;
  verbose?: boolean;
}
interface ArchiverPluginOptions {
  name?: string;
  outputDir?: string;
}
type HtmlPluginOptions = Options$1;
interface ImportmapPluginOptions {
  defaultProvider?: 'esm.sh' | 'jspm.io';
  importmap?: Array<{
    name: string;
    range?: string;
  }>;
  inputMap?: IImportMap;
}
interface ConditionPlugin {
  condition?: boolean;
  plugins: () => PluginOption[] | PromiseLike<PluginOption[]>;
}
interface CommonPluginOptions {
  devtools?: boolean;
  env?: Record<string, any>;
  injectMetadata?: boolean;
  isBuild?: boolean;
  mode?: string;
  visualizer?: boolean | PluginVisualizerOptions;
}
interface ApplicationPluginOptions extends CommonPluginOptions {
  archiver?: boolean;
  archiverPluginOptions?: ArchiverPluginOptions;
  compress?: boolean;
  compressTypes?: ('brotli' | 'gzip')[];
  dayjs?: boolean;
  extraAppConfig?: boolean;
  html?: boolean | HtmlPluginOptions;
  i18n?: boolean;
  importmap?: boolean;
  importmapOptions?: ImportmapPluginOptions;
  injectAppLoading?: boolean;
  injectGlobalScss?: boolean;
  license?: boolean;
  nitroMock?: boolean;
  nitroMockOptions?: NitroMockPluginOptions;
  print?: boolean;
  printInfoMap?: PrintPluginOptions['infoMap'];
  pwa?: boolean;
  pwaOptions?: Partial<Options>;
  vxeTableLazyImport?: boolean;
}
interface LibraryPluginOptions extends CommonPluginOptions {
  dts?: boolean | PluginOptions;
}
type ApplicationOptions = ApplicationPluginOptions;
type LibraryOptions = LibraryPluginOptions;
type DefineApplicationOptions = (config?: ConfigEnv) => Promise<{
  application?: ApplicationOptions;
  vite?: UserConfig;
}>;
type DefineLibraryOptions = (config?: ConfigEnv) => Promise<{
  library?: LibraryOptions;
  vite?: UserConfig;
}>;
type DefineConfig = DefineApplicationOptions | DefineLibraryOptions;
type VbenViteConfig = Promise<UserConfig> | UserConfig | UserConfigFnPromise;
declare function defineApplicationConfig(userConfigPromise?: DefineApplicationOptions): import("vite").UserConfigFnPromise;
declare function defineLibraryConfig(userConfigPromise?: DefineLibraryOptions): import("vite").UserConfigFnPromise;
declare function defineConfig(userConfigPromise?: DefineConfig, type?: 'application' | 'auto' | 'library'): VbenViteConfig;
declare const getDefaultPwaOptions: (name: string) => Partial<Options>;
declare const defaultImportmapOptions: ImportmapPluginOptions;
declare const viteArchiverPlugin: (options?: ArchiverPluginOptions) => PluginOption;
declare function viteDayjsPlugin(): Plugin;
declare function viteHtmlPlugin(options?: Options$1): PluginOption;
declare function viteVxeTableImportsPlugin(): Promise<PluginOption>;
declare function loadApplicationPlugins(options: ApplicationPluginOptions): Promise<PluginOption[]>;
declare function loadLibraryPlugins(options: LibraryPluginOptions): Promise<PluginOption[]>;
declare function loadAndConvertEnv(match?: string, confFiles?: string[]): Promise<Partial<ApplicationPluginOptions> & {
  appTitle: string;
  base: string;
  port: number;
}>;
export { type ApplicationPluginOptions, type ArchiverPluginOptions, type CommonPluginOptions, type ConditionPlugin, type DefineApplicationOptions, type DefineConfig, type DefineLibraryOptions, type HtmlPluginOptions, type IImportMap, type ImportmapPluginOptions, type LibraryPluginOptions, type NitroMockPluginOptions, type PrintPluginOptions, type VbenViteConfig, defaultImportmapOptions, defineApplicationConfig, defineConfig, defineLibraryConfig, getDefaultPwaOptions, loadAndConvertEnv, loadApplicationPlugins, loadLibraryPlugins, viteArchiverPlugin, viteCompressPlugin, viteDayjsPlugin, viteDtsPlugin, viteHtmlPlugin, viteVisualizerPlugin, viteVxeTableImportsPlugin };