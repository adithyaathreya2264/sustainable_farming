import { settings } from "./config.js";
import { createApp } from "./app.js";

const app = createApp();
app.listen(settings.port, "0.0.0.0", () => {
  console.log(`Sustainable Farming API listening on 0.0.0.0:${settings.port}`);
});
