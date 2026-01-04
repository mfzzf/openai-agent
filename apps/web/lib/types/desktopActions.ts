export type DesktopAction =
  | {
      action: "click";
      x: number;
      y: number;
      button?: "left" | "right" | "middle";
      double?: boolean;
    }
  | {
      action: "type";
      text: string;
      chunkSize?: number;
      delayInMs?: number;
    }
  | {
      action: "press";
      keys: string[];
    }
  | {
      action: "wait";
      ms: number;
    }
  | {
      action: "scroll";
      direction?: "up" | "down";
      amount?: number;
    }
  | {
      action: "moveMouse";
      x: number;
      y: number;
    }
  | {
      action: "drag";
      fromX: number;
      fromY: number;
      toX: number;
      toY: number;
    };

export type DesktopActionApiRequest = { threadId: string } & DesktopAction;

export type DesktopScreenshotApiRequest = {
  threadId: string;
  includeCursor?: boolean;
  includeScreenSize?: boolean;
};

export type DesktopScreenshotResult = {
  mime: "image/png";
  imageBase64: string;
  screenSize?: { width: number; height: number };
  cursorPosition?: { x: number; y: number };
};
