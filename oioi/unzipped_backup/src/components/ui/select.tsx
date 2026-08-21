"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

const Select = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<"div"> & { children?: React.ReactNode }
>(({ className, children, ...props }, ref) => (
  <div ref={ref} className={cn("relative w-full", className)} data-slot="select" {...props}>
    <SelectTrigger className="relative" />
    <SelectContent className="absolute z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-sm shadow-md">
      {children}
    </SelectContent>
  </div>
));
Select.displayName = "Select";

const SelectTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ComponentPropsWithoutRef<"button">
>(({ className, children, ...props }, ref) => (
  <button
    ref={ref}
    type="button"
    className={cn(
      "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 pr-8 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
      className
    )}
    {...props}
  >
    <span className="flex h-full items-center w-full placeholder:text-muted-foreground truncate">
      {children}
    </span>
    <ChevronDown className="h-4 w-4 text-muted-foreground ml-2 flex-shrink-0" />
  </button>
));
SelectTrigger.displayName = "SelectTrigger";

const SelectValue = React.forwardRef<
  HTMLSpanElement,
  React.ComponentPropsWithoutRef<"span">
>(({ className, children, ...props }, ref) => (
  <span ref={ref} className={cn("flex h-full items-center w-full placeholder:text-muted-foreground truncate", className)} {...props}>
    {children}
  </span>
));
SelectValue.displayName = "SelectValue";

const SelectItem = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<"div"> & { children?: React.ReactNode; disabled?: boolean; value?: string }
>(({ className, children, disabled, value, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "flex cursor-default select-none items-center rounded-sm py-1.5 pl-1 pr-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      className
    )}
    role="option"
    aria-disabled={disabled}
    aria-selected={value}
    {...props}
  >
    {children}
  </div>
));
SelectItem.displayName = "SelectItem";

const SelectContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<"div">
>(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-sm shadow-md",
      className
    )}
    {...props}
  >
    {children}
  </div>
));
SelectContent.displayName = "SelectContent";

export { Select, SelectTrigger, SelectValue, SelectItem, SelectContent };