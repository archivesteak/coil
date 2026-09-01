// Coil/Okio and Skiko reference Node APIs that require browser implementations
// when webpack bundles the Kotlin/JS test executable. Kotlin/Wasm loads through
// static/load.mjs and must not receive Node's process shim.
const isKotlinJsTest = (config.files || []).some((file) => {
  const pattern = typeof file === "string" ? file : file.pattern;
  return typeof pattern === "string" && /[/\\]kotlin[/\\].+\.js$/.test(pattern);
});

if (isKotlinJsTest) {
  const NodePolyfillPlugin = require("node-polyfill-webpack-plugin");
  config.webpack = config.webpack || {};
  config.webpack.plugins = config.webpack.plugins || [];
  config.webpack.plugins.push(new NodePolyfillPlugin());
}
