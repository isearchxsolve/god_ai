import { Layout } from "@/components/layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Settings as SettingsIcon, Save, Shield } from "lucide-react";

export default function Settings() {
  return (
    <Layout>
      <div className="space-y-6 max-w-4xl mx-auto">
        <div>
          <h1 className="text-3xl font-bold font-display uppercase tracking-widest text-white mb-2">
            System <span className="text-secondary text-glow">Configuration</span>
          </h1>
          <p className="text-muted-foreground text-sm font-mono">
            Manage your API keys, RPC endpoints, and trading parameters.
          </p>
        </div>

        <Card className="bg-card/40 border-border/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-primary" />
              RPC Connection
            </CardTitle>
            <CardDescription>Configure your Solana RPC provider endpoints.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="rpc">Primary RPC URL</Label>
              <Input 
                id="rpc" 
                placeholder="https://api.mainnet-beta.solana.com" 
                className="bg-black/20 border-white/10 focus:border-primary/50"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="ws">WebSocket URL</Label>
              <Input 
                id="ws" 
                placeholder="wss://api.mainnet-beta.solana.com" 
                className="bg-black/20 border-white/10 focus:border-primary/50"
              />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card/40 border-border/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle>Trading Parameters</CardTitle>
            <CardDescription>Safety checks and limits for automated trading.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="text-base">Auto-Snipe New Pairs</Label>
                <p className="text-sm text-muted-foreground">Automatically buy new tokens detected in mempool</p>
              </div>
              <Switch />
            </div>
            <Separator className="bg-white/10" />
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="grid gap-2">
                <Label>Max Slippage (%)</Label>
                <Input type="number" defaultValue="15" className="bg-black/20 border-white/10" />
              </div>
              <div className="grid gap-2">
                <Label>Priority Fee (SOL)</Label>
                <Input type="number" defaultValue="0.005" className="bg-black/20 border-white/10" />
              </div>
              <div className="grid gap-2">
                <Label>Take Profit (%)</Label>
                <Input type="number" defaultValue="100" className="bg-black/20 border-white/10" />
              </div>
              <div className="grid gap-2">
                <Label>Stop Loss (%)</Label>
                <Input type="number" defaultValue="50" className="bg-black/20 border-white/10" />
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end gap-4">
          <Button variant="outline" className="border-border">Cancel</Button>
          <Button className="bg-primary text-black hover:bg-primary/90">
            <Save className="h-4 w-4 mr-2" />
            Save Configuration
          </Button>
        </div>
      </div>
    </Layout>
  );
}
