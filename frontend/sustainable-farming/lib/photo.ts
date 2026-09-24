import * as ImagePicker from "expo-image-picker";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";

/**
 * Pick or take one photo for a model check, then re-encode it:
 *
 * - resized to at most 1280 px wide (every model resizes to <= 800 px anyway,
 *   so this only saves upload time on a rural connection);
 * - re-encoded as JPEG, which also drops EXIF metadata - including GPS - before
 *   the photo leaves the phone. Orientation is baked into the pixels first.
 *
 * Returns null if the farmer cancels or denies permission.
 */
export type PhotoSource = "camera" | "library";

export interface PreparedPhoto {
  uri: string;
  width: number;
  height: number;
}

const MAX_WIDTH = 1280;

export async function pickPhoto(source: PhotoSource): Promise<PreparedPhoto | null> {
  const permission =
    source === "camera"
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!permission.granted) return null;

  const options: ImagePicker.ImagePickerOptions = {
    mediaTypes: ["images"],
    quality: 1,
    exif: false,
  };
  const result =
    source === "camera"
      ? await ImagePicker.launchCameraAsync(options)
      : await ImagePicker.launchImageLibraryAsync(options);
  if (result.canceled || !result.assets?.length) return null;

  const asset = result.assets[0];
  const context = ImageManipulator.manipulate(asset.uri);
  if (asset.width > MAX_WIDTH) context.resize({ width: MAX_WIDTH });
  const rendered = await context.renderAsync();
  const saved = await rendered.saveAsync({ format: SaveFormat.JPEG, compress: 0.8 });
  return { uri: saved.uri, width: saved.width, height: saved.height };
}
