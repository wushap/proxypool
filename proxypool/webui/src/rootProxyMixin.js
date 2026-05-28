import { appOptions } from "./appOptions";

const dataKeys = Object.keys(appOptions.data ? appOptions.data() : {});
const computedKeys = Object.keys(appOptions.computed || {});
const methodKeys = Object.keys(appOptions.methods || {});

const proxiedComputed = {};
for (const key of [...dataKeys, ...computedKeys]) {
  proxiedComputed[key] = {
    get() {
      return this.appState?.[key];
    },
    set(value) {
      if (this.appState) this.appState[key] = value;
    },
  };
}

const proxiedMethods = {};
for (const key of methodKeys) {
  proxiedMethods[key] = function (...args) {
    return this.appState[key](...args);
  };
}

export const rootProxyMixin = {
  inject: ["appState"],
  computed: proxiedComputed,
  methods: proxiedMethods,
};
