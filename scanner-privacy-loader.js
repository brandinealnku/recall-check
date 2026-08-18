(() => {
  "use strict";

  const ZXING_URL = "https://cdn.jsdelivr.net/npm/@zxing/browser@0.1.5/umd/zxing-browser.min.js";
  let loadPromise = null;
  let realZXing = null;

  function loadZXing() {
    if (realZXing) return Promise.resolve(realZXing);
    if (loadPromise) return loadPromise;

    loadPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = ZXING_URL;
      script.async = true;
      script.crossOrigin = "anonymous";
      script.referrerPolicy = "no-referrer";
      script.onload = () => {
        const loaded = window.ZXingBrowser;
        if (!loaded || loaded === lazyFacade) {
          reject(new Error("scanner_library_unavailable"));
          return;
        }
        realZXing = loaded;
        window.ZXingBrowser = realZXing;
        resolve(realZXing);
      };
      script.onerror = () => reject(new Error("scanner_library_blocked"));
      document.head.appendChild(script);
    }).catch(error => {
      loadPromise = null;
      window.ZXingBrowser = lazyFacade;
      throw error;
    });

    return loadPromise;
  }

  class LazyBrowserMultiFormatReader {
    constructor(...args) {
      this.args = args;
      this.reader = null;
    }

    async decodeFromConstraints(...args) {
      const lib = await loadZXing();
      this.reader = new lib.BrowserMultiFormatReader(...this.args);
      return this.reader.decodeFromConstraints(...args);
    }

    reset(...args) {
      return this.reader?.reset?.(...args);
    }
  }

  const lazyFacade = {
    BrowserMultiFormatReader: LazyBrowserMultiFormatReader,
    BrowserCodeReader: {
      async listVideoInputDevices(...args) {
        const lib = await loadZXing();
        return lib.BrowserCodeReader.listVideoInputDevices(...args);
      }
    }
  };

  if (!window.ZXingBrowser) window.ZXingBrowser = lazyFacade;
  window.RecallCheckScannerLoader = Object.freeze({ load: loadZXing });
})();
