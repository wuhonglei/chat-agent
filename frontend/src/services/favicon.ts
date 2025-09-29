export const checkGoogleFavIconsAvailable = async (): Promise<boolean> => {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000); // 5秒超时

    const response = await fetch(
      "https://www.google.com/s2/favicons?domain=www.baidu.com",
      {
        signal: controller.signal,
        mode: "cors",
        method: "GET",
      }
    );

    clearTimeout(timeoutId);

    // 检查响应状态码是否成功 (2xx)
    return response.ok;
  } catch (error) {
    console.error("Google Favicons API 检测失败:", error);
    return false;
  }
};
