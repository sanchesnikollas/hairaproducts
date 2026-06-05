/**
 * Conteúdo Moon — hub com 4 abas pra gerenciar a inteligência da Moon.
 *
 * 1. Identidade & Tom   — editor das chaves moon_config (system_prompt + intents)
 * 2. Material           — upload/preview/delete dos docs proprietários (KB)
 * 3. Como Moon decide   — visualização passo-a-passo do fluxo (sem dado dinâmico)
 * 4. Métricas           — feedback summary + recent downvotes (admin-only no BE)
 */
import { useState } from 'react';
import { motion } from 'motion/react';
import { BookOpen, MessageCircleHeart, FolderOpen, Workflow, BarChart3, ShieldCheck } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import IdentityTab from './sections/IdentityTab';
import MaterialTab from './sections/MaterialTab';
import WorkflowTab from './sections/WorkflowTab';
import MetricsTab from './sections/MetricsTab';
import AuditTab from './sections/AuditTab';

export default function OpsKnowledge() {
  const [tab, setTab] = useState<string>('identity');

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="font-display text-3xl font-semibold text-ink flex items-center gap-2">
          <BookOpen className="text-[#ff5900]" /> Conteúdo Moon
        </h1>
        <p className="text-sm text-ink-muted mt-1 max-w-2xl">
          Tudo que define como a Moon pensa, fala e responde. Ajustes valem na próxima
          conversa — sem precisar de redeploy.
        </p>
      </motion.div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="grid grid-cols-5 max-w-3xl">
          <TabsTrigger value="identity" className="gap-2">
            <MessageCircleHeart size={14} /> Identidade & Tom
          </TabsTrigger>
          <TabsTrigger value="material" className="gap-2">
            <FolderOpen size={14} /> Material
          </TabsTrigger>
          <TabsTrigger value="workflow" className="gap-2">
            <Workflow size={14} /> Como decide
          </TabsTrigger>
          <TabsTrigger value="metrics" className="gap-2">
            <BarChart3 size={14} /> Métricas
          </TabsTrigger>
          <TabsTrigger value="audit" className="gap-2">
            <ShieldCheck size={14} /> Auditoria
          </TabsTrigger>
        </TabsList>

        <TabsContent value="identity" className="mt-6">
          <IdentityTab />
        </TabsContent>
        <TabsContent value="material" className="mt-6">
          <MaterialTab />
        </TabsContent>
        <TabsContent value="workflow" className="mt-6">
          <WorkflowTab />
        </TabsContent>
        <TabsContent value="metrics" className="mt-6">
          <MetricsTab />
        </TabsContent>
        <TabsContent value="audit" className="mt-6">
          <AuditTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
