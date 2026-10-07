export function getCategoryById(taxonomy, categoryId) {
  if (!taxonomy || !Array.isArray(taxonomy.categories)) {
    throw new Error("Taxonomia inválida: lista de categorias ausente.");
  }

  const category = taxonomy.categories.find(({ id }) => id === categoryId);

  if (!category) {
    throw new Error(`Classificação desconhecida na taxonomia: ${categoryId}.`);
  }

  const requiredFields = ["id", "name", "description", "severity", "consequence"];
  const missingField = requiredFields.find((field) => !category[field]);

  if (missingField) {
    throw new Error(`Categoria ${categoryId} sem o campo ${missingField}.`);
  }

  return category;
}
