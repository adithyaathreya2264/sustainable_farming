import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "../locales/en.json";
import kn from "../locales/kn.json";
import hi from "../locales/hi.json";
import ta from "../locales/ta.json";
import te from "../locales/te.json";
import ml from "../locales/ml.json";
import pa from "../locales/pa.json";
import bn from "../locales/bn.json";
import gu from "../locales/gu.json";
import mni from "../locales/mni.json";

i18n.use(initReactI18next).init({
  compatibilityJSON: "v4",
  resources: {
    en: { translation: en },
    kn: { translation: kn },
    hi: { translation: hi },
    ta: { translation: ta },
    te: { translation: te },
    ml: { translation: ml },
    pa: { translation: pa },
    bn: { translation: bn },
    gu: { translation: gu },
    mni: { translation: mni },
  },
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
