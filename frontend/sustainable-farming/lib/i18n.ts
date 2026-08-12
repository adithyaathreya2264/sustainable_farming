import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "../locales/en.json";
import kn from "../locales/kn.json";
import hi from "../locales/hi.json";

i18n.use(initReactI18next).init({
  compatibilityJSON: "v4",
  resources: {
    en: { translation: en },
    // Kannada/Hindi translation files are stubbed empty for now — i18next
    // falls back to English for any missing key until they're populated.
    kn: { translation: kn },
    hi: { translation: hi },
  },
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
