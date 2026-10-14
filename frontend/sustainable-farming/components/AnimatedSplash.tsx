import React, { useEffect, useMemo, useRef, useState } from "react";
import { AccessibilityInfo, Animated, Easing, Image, StyleSheet, useWindowDimensions } from "react-native";

/**
 * Launch screen, drawn over the app while the store hydrates.
 *
 * Hand-off from the native splash: expo-splash-screen shows assets/splash-icon.png
 * at `imageWidth` (app.json) on BG, centered. The first frame here is that same
 * picture at the same size and position, so hiding the native splash is
 * invisible. The only motion is the name easing in under the logo, then a fade
 * out once the app is ready.
 */

const BG = "#021F12";
const CREAM = "#FFF3C4";

// Must match expo-splash-screen's imageWidth in app.json, and the tile's
// share of splash-icon.png's canvas.
const BOX = 288;
const TILE_FRACTION = 0.62;

const TITLE = "Chiguru Nele";
const MIN_VISIBLE_MS = 1800;
const EXIT_MS = 350;

interface Props {
  /** True once the app behind the splash can be shown. */
  ready: boolean;
  /** Called when the splash has finished fading out. */
  onFinish: () => void;
  /** Called once the logo is drawn, so the native splash can be hidden. */
  onLogoReady: () => void;
}

export function AnimatedSplash({ ready, onFinish, onLogoReady }: Props) {
  const { width, height } = useWindowDimensions();
  const [reduceMotion, setReduceMotion] = useState<boolean | null>(null);
  const [minElapsed, setMinElapsed] = useState(false);
  const exiting = useRef(false);
  const logoReported = useRef(false);

  const title = useMemo(() => new Animated.Value(0), []);
  const exit = useMemo(() => new Animated.Value(0), []);

  const reportLogoReady = () => {
    if (logoReported.current) return;
    logoReported.current = true;
    onLogoReady();
  };

  useEffect(() => {
    // Never leave the native splash up if the image somehow doesn't report in.
    const id = setTimeout(reportLogoReady, 1200);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled()
      .then(setReduceMotion)
      .catch(() => setReduceMotion(false));
  }, []);

  useEffect(() => {
    if (reduceMotion === null) return;
    if (reduceMotion) {
      title.setValue(1);
    } else {
      Animated.timing(title, {
        toValue: 1,
        duration: 600,
        delay: 350,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }).start();
    }
    const id = setTimeout(() => setMinElapsed(true), reduceMotion ? 700 : MIN_VISIBLE_MS);
    return () => clearTimeout(id);
  }, [reduceMotion, title]);

  useEffect(() => {
    if (!ready || !minElapsed || exiting.current) return;
    exiting.current = true;
    Animated.timing(exit, {
      toValue: 1,
      duration: EXIT_MS,
      easing: Easing.in(Easing.quad),
      useNativeDriver: true,
    }).start(({ finished }) => {
      if (finished) onFinish();
    });
  }, [ready, minElapsed, onFinish, exit]);

  const tile = BOX * TILE_FRACTION;
  const titleTop = height / 2 + tile / 2 + 32;

  return (
    <Animated.View
      accessibilityLabel={TITLE}
      style={[
        StyleSheet.absoluteFill,
        { backgroundColor: BG, opacity: exit.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }) },
      ]}
    >
      <Image
        source={require("../assets/splash-icon.png")}
        style={{ position: "absolute", left: (width - BOX) / 2, top: (height - BOX) / 2, width: BOX, height: BOX }}
        resizeMode="contain"
        fadeDuration={0}
        onLoad={reportLogoReady}
      />
      <Animated.Text
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: titleTop,
          textAlign: "center",
          fontSize: 30,
          fontWeight: "600",
          letterSpacing: 1.5,
          color: CREAM,
          opacity: title,
          transform: [{ translateY: title.interpolate({ inputRange: [0, 1], outputRange: [8, 0] }) }],
        }}
      >
        {TITLE}
      </Animated.Text>
    </Animated.View>
  );
}
