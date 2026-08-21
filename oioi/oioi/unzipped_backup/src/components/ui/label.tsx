import * as React from "react";
import { Slot } from "@radix-ui/react-label";

export const Label = React.forwardRef<
  HTMLLabelElement,
  React.ComponentPropsWithoutRef<typeof Slot>
>(({ className, ...props }, ref) => (
  <label
    className={
      "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70" +
        (className ? ` ${className}` : "")
    }
    ref={ref}
    {...props}
  />
));
Label.displayName = "Label";

const SlotSlot = Slot;