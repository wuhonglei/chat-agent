export function isImageFile(file: File) {
  return file.type.startsWith("image/");
}

export function isImageSizeUnderLimit(file: File, limit_bytes: number) {
  return file.size <= limit_bytes;
}

/**
 * Check if the file is a valid avatar image
 * @param file - The file to check
 * @returns True if the file is a valid avatar image, false otherwise
 */
export function isValidAvatarImage(file: File) {
  return isImageFile(file) && isImageSizeUnderLimit(file, 1024 * 1024 * 2); // 2MB
}
