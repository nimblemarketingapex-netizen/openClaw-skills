import requests
from typing import Dict, Any, List


class RecipeSkill:
    name = "recipes"
    version = "2.2.0"
    description = "Recipes by ingredients, cuisine, and mood"

    API_URL = "https://www.themealdb.com/api/json/v1/1"

    # ---------- helpers ----------

    def _success(self, data: Any) -> Dict:
        return {"success": True, "data": data}

    def _error(self, message: str) -> Dict:
        return {"success": False, "error": message}

    # ---------- поиск по холодильнику ----------

    def by_fridge(self, ingredients: List[str]) -> Dict:
        """
        Поиск рецептов по продуктам (холодильник).
        ingredients: ["chicken", "rice"]
        """
        if not ingredients:
            return self._error("No ingredients provided")

        query = ",".join(ingredients)
        url = f"{self.API_URL}/filter.php?i={query}"

        try:
            r = requests.get(url, timeout=10)

            if r.status_code != 200:
                return self._error("API error")

            try:
                data = r.json()
            except Exception:
                return self._error("Invalid API response")

            if not data or not data.get("meals"):
                return self._error("No recipes found")

            return self._success({
                "ingredients": ingredients,
                "recipes": data["meals"]
            })

        except Exception as e:
            return self._error(str(e))

    # ---------- полный рецепт ----------

    def get_recipe(self, recipe_id: str) -> Dict:
        """
        Получить рецепт по ID.
        """
        url = f"{self.API_URL}/lookup.php?i={recipe_id}"

        try:
            r = requests.get(url, timeout=10)

            if r.status_code != 200:
                return self._error("API error")

            try:
                data = r.json()
            except Exception:
                return self._error("Invalid API response")

            if not data or not data.get("meals"):
                return self._error("Recipe not found")

            meal = data["meals"][0]

            return self._success({
                "title": meal.get("strMeal"),
                "category": meal.get("strCategory"),
                "area": meal.get("strArea"),
                "instructions": meal.get("strInstructions"),
                "ingredients": self._extract_ingredients(meal),
                "image": meal.get("strMealThumb")
            })

        except Exception as e:
            return self._error(str(e))

    # ---------- кухня (cuisine) ----------

    def by_cuisine(self, area: str) -> Dict:
        """
        Поиск по кухне (итальянская, азиатская и т.д.)

        area:
        - Italian
        - Chinese
        - Mexican
        - Japanese
        - etc.
        """
        if not area:
            return self._error("No cuisine provided")

        url = f"{self.API_URL}/filter.php?a={area}"

        try:
            r = requests.get(url, timeout=10)

            if r.status_code != 200:
                return self._error("API error")

            try:
                data = r.json()
            except Exception:
                return self._error("Invalid API response")

            if not data or not data.get("meals"):
                return self._error("No recipes for this cuisine")

            return self._success({
                "cuisine": area,
                "recipes": data["meals"]
            })

        except Exception as e:
            return self._error(str(e))

    # ---------- извлечение ингредиентов ----------

    def _extract_ingredients(self, meal: Dict) -> List[str]:
        ingredients = []

        for i in range(1, 21):
            ing = meal.get(f"strIngredient{i}")
            measure = meal.get(f"strMeasure{i}") or ""

            if ing and ing.strip():
                ingredients.append(f"{ing} - {measure}".strip())

        return ingredients

    # ---------- советы по настроению ----------

    def suggest(self, mood: str = "quick") -> Dict:
        """
        Советы по типу блюда.

        mood:
        - quick
        - party
        - comfort
        - healthy
        """
        base = {
            "quick": "Быстрое блюдо",
            "party": "Праздничное",
            "comfort": "Уютное",
            "healthy": "Полезное"
        }

        style = base.get(mood, "Рекомендация")
        suggestion = f"{style} блюдо"

        return self._success({
            "mood": mood,
            "suggestion": suggestion
        })

    # ---------- умный подбор ----------

    def smart_recipe(self, ingredients: List[str], mood: str = "quick") -> Dict:
        """
        Умный сценарий:
        1) поиск по холодильнику
        2) если нет — совет
        """
        recipes = self.by_fridge(ingredients)

        if recipes["success"] and recipes["data"].get("recipes"):
            return recipes

        return self.suggest(mood)

# singleton
skill = RecipeSkill()