export const checkGoogleFavIconsAvailable = async (): Promise<boolean> => {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const timeoutId = setTimeout(() => {
      reject(new Error("Google Favicons API 检测超时"));
    }, 5000);

    img.onload = () => {
      clearTimeout(timeoutId);
      resolve(true);
    };
    img.onerror = () => {
      clearTimeout(timeoutId);
      resolve(false);
    };

    img.src = "https://www.google.com/s2/favicons?domain=www.baidu.com";
  });
};
