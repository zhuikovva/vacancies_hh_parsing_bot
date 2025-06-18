from catboost import CatBoostClassifier, CatBoostRegressor, Pool

import logging

logger = logging.getLogger(__name__)

class MlModels:
    def __init__(self):
        self.model_grade_path = "models/grade_model_new.cbm"
        self.model_salary_path = "models/salary_model_new.cbm"
        self.grade_model = CatBoostClassifier().load_model(self.model_grade_path)
        self.salary_model = CatBoostRegressor().load_model(self.model_salary_path)
        

    def predict_grade(self, features):
        cat_features = ['schedule', 'experience']
        text_features = ['vacancy_name', 'key_skills', 'description']
        pool = Pool(data=features, cat_features=cat_features, text_features=text_features)
        grade = self.grade_model.predict(pool)
        #logger.info(f"Прогноз: {grade}")
        return str(grade[0, 0])
    
    def predict_salary(self, features):
        cat_features = ['schedule', 'grade', 'experience']
        text_features = ['vacancy_name', 'key_skills', 'description']

        pool = Pool(data=features, cat_features=cat_features, text_features=text_features)
        salary = self.salary_model.predict(pool)
        return salary[0]
        