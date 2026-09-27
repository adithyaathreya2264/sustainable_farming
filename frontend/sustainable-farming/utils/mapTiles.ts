/**
 * MapTiler raw XYZ raster tiles (https://api.maptiler.com/maps/hybrid/{z}/{x}/{y}.jpg),
 * confirmed working for this project's key — MapTiler's Static Maps API
 * (a single pre-composed image) rejected the same key ("Invalid key"), which
 * on investigation is a plan/product restriction on that specific endpoint,
 * not a bad key: `/maps/hybrid/tiles.json` with the same key returns a
 * normal TileJSON descriptor. So components/FieldBoundaryMap.tsx composites
 * a small grid of these tiles itself instead of requesting one static image.
 *
 * Plain <Image> tiles, not a map SDK, so this still works inside Expo Go —
 * @rnmapbox/maps or react-native-maps would need a custom dev client.
 */

const MAP_TILER_API_KEY = process.env.EXPO_PUBLIC_MAP_TILER_API_KEY ?? "";

export const MAP_TILER_AVAILABLE = MAP_TILER_API_KEY.length > 0;

/** Satellite imagery with place/road labels — the most useful background for
 * identifying a real field, confirmed available on this key via tiles.json. */
const STYLE = "hybrid";

export const TILE_SIZE = 256;

export function tileUrl(z: number, x: number, y: number): string {
  return `https://api.maptiler.com/maps/${STYLE}/${z}/${x}/${y}.jpg?key=${MAP_TILER_API_KEY}`;
}

/** Web Mercator world-pixel X for a longitude at a given zoom (0..256*2^zoom). */
export function lonToWorldX(lonDeg: number, zoom: number): number {
  return ((lonDeg + 180) / 360) * TILE_SIZE * 2 ** zoom;
}

/** Web Mercator world-pixel Y for a latitude at a given zoom. */
export function latToWorldY(latDeg: number, zoom: number): number {
  const latRad = (latDeg * Math.PI) / 180;
  return (
    ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) *
    TILE_SIZE *
    2 ** zoom
  );
}

/** Standard Web Mercator ground resolution at a given latitude/zoom — used to
 * convert canvas taps to real coordinates on the same projection the tiles
 * above are drawn in. */
export function metersPerPixel(latDeg: number, zoom: number): number {
  return (156543.03392 * Math.cos((latDeg * Math.PI) / 180)) / 2 ** zoom;
}

export interface PlacedTile {
  key: string;
  url: string;
  left: number;
  top: number;
}

/** The grid of 256px tiles needed to cover a `width`x`height` canvas centered
 * on `origin`, each with its pixel offset within that canvas. */
export function tilesForCanvas(
  origin: { lat: number; long: number },
  canvas: { width: number; height: number },
  zoom: number
): PlacedTile[] {
  const maxIndex = 2 ** zoom - 1;
  const originWorldX = lonToWorldX(origin.long, zoom);
  const originWorldY = latToWorldY(origin.lat, zoom);
  const topLeftWorldX = originWorldX - canvas.width / 2;
  const topLeftWorldY = originWorldY - canvas.height / 2;

  const xMin = Math.floor(topLeftWorldX / TILE_SIZE);
  const xMax = Math.floor((topLeftWorldX + canvas.width) / TILE_SIZE);
  const yMin = Math.max(0, Math.floor(topLeftWorldY / TILE_SIZE));
  const yMax = Math.min(maxIndex, Math.floor((topLeftWorldY + canvas.height) / TILE_SIZE));

  const tiles: PlacedTile[] = [];
  for (let y = yMin; y <= yMax; y++) {
    for (let x = xMin; x <= xMax; x++) {
      // Wrap horizontally (antimeridian) rather than requesting an
      // out-of-range tile index.
      const wrappedX = ((x % (maxIndex + 1)) + (maxIndex + 1)) % (maxIndex + 1);
      tiles.push({
        key: `${zoom}/${wrappedX}/${y}`,
        url: tileUrl(zoom, wrappedX, y),
        left: x * TILE_SIZE - topLeftWorldX,
        top: y * TILE_SIZE - topLeftWorldY,
      });
    }
  }
  return tiles;
}
