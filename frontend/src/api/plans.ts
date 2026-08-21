import { apiClient } from "./client";
import type { Plan } from "./types";

export type PlanInput = Omit<Plan, "id">;

export async function listPlans(): Promise<Plan[]> {
  const { data } = await apiClient.get<Plan[]>("/plans");
  return data;
}

export async function createPlan(payload: PlanInput): Promise<Plan> {
  const { data } = await apiClient.post<Plan>("/plans", payload);
  return data;
}

export async function updatePlan(id: string, payload: Partial<PlanInput>): Promise<Plan> {
  const { data } = await apiClient.patch<Plan>(`/plans/${id}`, payload);
  return data;
}

export async function deletePlan(id: string): Promise<void> {
  await apiClient.delete(`/plans/${id}`);
}
