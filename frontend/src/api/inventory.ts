import { apiClient } from "./client";
import type {
  InventoryItem,
  InventoryItemInput,
  InventoryMovement,
  InventoryMovementInput,
  Supplier,
  SupplierInput,
  TechnicianBalance,
} from "./types";

export async function listSuppliers(): Promise<Supplier[]> {
  const { data } = await apiClient.get<Supplier[]>("/suppliers");
  return data;
}

export async function createSupplier(payload: SupplierInput): Promise<Supplier> {
  const { data } = await apiClient.post<Supplier>("/suppliers", payload);
  return data;
}

export async function updateSupplier(id: string, payload: Partial<SupplierInput>): Promise<Supplier> {
  const { data } = await apiClient.patch<Supplier>(`/suppliers/${id}`, payload);
  return data;
}

export async function deleteSupplier(id: string): Promise<void> {
  await apiClient.delete(`/suppliers/${id}`);
}

export async function listInventoryItems(): Promise<InventoryItem[]> {
  const { data } = await apiClient.get<InventoryItem[]>("/inventory-items");
  return data;
}

export async function createInventoryItem(payload: InventoryItemInput): Promise<InventoryItem> {
  const { data } = await apiClient.post<InventoryItem>("/inventory-items", payload);
  return data;
}

export async function updateInventoryItem(
  id: string,
  payload: Partial<InventoryItemInput>,
): Promise<InventoryItem> {
  const { data } = await apiClient.patch<InventoryItem>(`/inventory-items/${id}`, payload);
  return data;
}

export async function deleteInventoryItem(id: string): Promise<void> {
  await apiClient.delete(`/inventory-items/${id}`);
}

export async function listItemMovements(itemId: string): Promise<InventoryMovement[]> {
  const { data } = await apiClient.get<InventoryMovement[]>(`/inventory-items/${itemId}/movements`);
  return data;
}

export async function createInventoryMovement(
  payload: InventoryMovementInput,
): Promise<InventoryMovement> {
  const { data } = await apiClient.post<InventoryMovement>("/inventory-movements", payload);
  return data;
}

export async function getBalanceByTechnician(): Promise<TechnicianBalance[]> {
  const { data } = await apiClient.get<TechnicianBalance[]>("/inventory/balance-by-technician");
  return data;
}
