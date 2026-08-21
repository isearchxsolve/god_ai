import * as React from "react";

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={
      "rounded-xl border bg-card text-card-foreground shadow-sm" +
        (className ? ` ${className}` : "")
    }
    {...props}
  />
));
Card.displayName = "Card";

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={
      "flex flex-col space-y-1.5 p-6" +
        (className ? ` ${className}` : "")
    }
    {...props}
  />
));
CardHeader.displayName = "CardHeader";

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={
      "p-6 pt-0" +
        (className ? ` ${className}` : "")
    }
    {...props}
  />
));
CardContent.displayName = "CardContent";

export { Card, CardHeader, CardContent };