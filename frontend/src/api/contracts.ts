import { apiClient } from "./client";
import type {
  Contract,
  ContractCreateInput,
  ContractSignInput,
  ContractTemplate,
  ContractTemplateInput,
} from "./types";

export async function listContractTemplates(): Promise<ContractTemplate[]> {
  const { data } = await apiClient.get<ContractTemplate[]>("/contract-templates");
  return data;
}

export async function createContractTemplate(payload: ContractTemplateInput): Promise<ContractTemplate> {
  const { data } = await apiClient.post<ContractTemplate>("/contract-templates", payload);
  return data;
}

export async function updateContractTemplate(
  id: string,
  payload: Partial<ContractTemplateInput>,
): Promise<ContractTemplate> {
  const { data } = await apiClient.patch<ContractTemplate>(`/contract-templates/${id}`, payload);
  return data;
}

export async function deleteContractTemplate(id: string): Promise<void> {
  await apiClient.delete(`/contract-templates/${id}`);
}

export async function listContracts(): Promise<Contract[]> {
  const { data } = await apiClient.get<Contract[]>("/contracts");
  return data;
}

export async function getContract(id: string): Promise<Contract> {
  const { data } = await apiClient.get<Contract>(`/contracts/${id}`);
  return data;
}

export async function createContract(payload: ContractCreateInput): Promise<Contract> {
  const { data } = await apiClient.post<Contract>("/contracts", payload);
  return data;
}

export async function signContract(id: string, payload: ContractSignInput): Promise<Contract> {
  const { data } = await apiClient.post<Contract>(`/contracts/${id}/sign`, payload);
  return data;
}

export async function voidContract(id: string): Promise<void> {
  await apiClient.post(`/contracts/${id}/void`);
}

export async function deleteContract(id: string): Promise<void> {
  await apiClient.delete(`/contracts/${id}`);
}
