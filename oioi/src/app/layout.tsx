import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'OiiOii — AI Animation Agent Team',
  description:
    'Turn ideas into characters, scenes, storyboards, and short films with 25+ AI models, 150+ styles, and a 7-agent animation team.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-bg-base text-fg-primary antialiased" suppressHydrationWarning>{children}</body>
    </html>
  );
}
