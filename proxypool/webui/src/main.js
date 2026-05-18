import { createApp } from "vue";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import "./styles/main.css";
import App from "./App.vue";

const app = createApp(App);

const applyElementPlusDefaults = () => {
  const defaults = [
    [ElementPlus.ElButton, { size: "small" }],
    [ElementPlus.ElTag, { size: "small", effect: "plain" }],
    [ElementPlus.ElInput, { size: "small", clearable: true }],
    [ElementPlus.ElSelect, { size: "small", clearable: true }],
  ];
  defaults.forEach(([component, props]) => {
    if (component && typeof component.setPropsDefaults === "function") {
      component.setPropsDefaults(props);
    }
  });
};

applyElementPlusDefaults();
app.use(ElementPlus);
app.mount("#app");
