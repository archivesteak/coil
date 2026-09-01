// Coil/Okio and Skiko reference Node APIs that require browser implementations
// when webpack bundles the JS test executable.
const NodePolyfillPlugin = require("node-polyfill-webpack-plugin");

config.webpack = config.webpack || {};
config.webpack.plugins = config.webpack.plugins || [];
config.webpack.plugins.push(new NodePolyfillPlugin());
