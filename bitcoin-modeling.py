import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier, OneVsOneClassifier
from sklearn.preprocessing import LabelBinarizer
from sklearn.linear_model import LogisticRegression, RidgeClassifier, SGDClassifier
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.svm import LinearSVC
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import confusion_matrix, plot_confusion_matrix, accuracy_score, roc_auc_score
from sklearn.model_selection import cross_validate
from sklearn.neighbors import NearestCentroid, KNeighborsClassifier
from sklearn.model_selection import train_test_split
from sklearn import preprocessing 

from utils import model_search, preprocessor, MasterModel

def main():
    
    print("Performing preprocessing and dataframe generation")
    # year and date can be used for classifying families because our 
    # model performs retroactive classification
    raw_df.drop(['Unnamed: 0'], axis=1, inplace=True)
    raw_df_test.drop(['Unnamed: 0'], axis=1, inplace=True)
    raw_df.sort_values(by=['year', 'day'], inplace=True)
    raw_df.reset_index(drop=True, inplace=True)
    
    df = preprocessor(raw_df)

    features = [c for c in df.columns if c not in ['label']]

    # specify only working on classifying families given a transaction is ransomware
    df_ransom = preprocessor(raw_df.loc[raw_df.label != 28])
    # filter for families with more occurances than 4 to allow for cross validation
    df_subset = df_ransom[~df_ransom.label.isin(df_ransom.label.value_counts()[df_ransom.label.value_counts()<=4].index.to_list())]
    
    testing_data = [{'param_dist': { 'objective': 'binary:logistic', 'verbosity':0, 'n_estimators':2},
                'clf': xgb.XGBClassifier,
                'name': 'xgb',
                'ovr': True},
                {'param_dist': {'objective':'multi:softmax', 'verbosity':0, 'num_class': 28, 'n_estimators':2},
                'clf': xgb.XGBClassifier,
                'name': 'xgb multi inherent',
                'ovr': False},
                {'param_dist': {'class_weight': 'balanced', },
                'clf': ExtraTreesClassifier,
                'name': 'et',
                'ovr': False},
                {'param_dist': {},
                'clf': MLPClassifier,
                'name': 'mlp',
                'ovr': False},
                {'param_dist': {'class_weight': 'balanced', },
                'clf': RidgeClassifier,
                'name': 'ridge',
                'ovr': False},
                {'param_dist': {},
                'clf': KNeighborsClassifier,
                'name': 'kneighbors',
                'ovr': False},
                {'param_dist': {'class_weight': 'balanced', },
                'clf': SGDClassifier,
                'name': 'sgd',
                'ovr': False},
                {'param_dist': {'class_weight': 'balanced', 'multi_class': 'ovr'},
                'clf': LinearSVC,
                'name': 'lsvc',
                'ovr': False},
               {'param_dist': {'class_weight': 'balanced', },
                'clf': RandomForestClassifier,
                'name': 'rf',
                'ovr': True},
               {'param_dist': {'class_weight': 'balanced', 'multi_class': 'ovr'},
                'clf': LogisticRegression,
                'name': 'lr ovr',
                'ovr': False},
                {'param_dist': {'class_weight': 'balanced', 'multi_class': 'multinomial'},
                'clf': LogisticRegression,
                'name': 'lr multiclass',
                'ovr': False},]

    print("|"*40)
    print("Searching for best ransomware families classifier")
    print("|"*40)
    X = df_subset[features]
    y = df_subset.label

    X_train,X_test,y_train,y_test=train_test_split(X,y,test_size=0.25,random_state=0)
    all_clfs, df_scores = model_search(X_train, X_test, y_train,  testing_data)
    
    print(df_scores)
    
    print("\n")
    print("Generating final multiclass ransom family classifier (chosen from the highest performance...)")
    # reinitialize X and y to include ALL ransom families
    X = df_subset[features]
    y = df_subset.label

    X_train,X_test,y_train,y_test=train_test_split(X,y,test_size=0.40, random_state=22)

    multiclassClf = RandomForestClassifier
    multiclassClf = multiclassClf(class_weight='balanced').fit(X_train, y_train)
    # obtain class probabilities
    y_prob = multiclassClf.predict_proba(X_test)

    # score based on weighted roc auc
    score = roc_auc_score(y_test, y_prob, average='weighted', multi_class='ovr')

    print("Random Forest roc auc wieghted score: ", score)
    print("-"*40)
    print("\nGenerating dictionary of known ransomware addresses...")
    X = df[features]
    y = df.label

    # manifest the dictionary of known addresses
    dict_known_address = {}

    for i, row in df.iterrows():
        if row.label != 28:
            if row.address not in dict_known_address:
                dict_known_address.update({row.address: row.label})
    print("-"*40)
    print("\nBuilding the binary classifier (whether or not a transaction is ransomware)")
    binaryClf = RandomForestClassifier

    # reinitialize X and y to include ALL ransom families
    X = df[features]
    y = (df.label == 28).astype(int)

    X_train,X_test,y_train,y_test=train_test_split(X,y,test_size=0.40, random_state=22)

    binaryClf = RandomForestClassifier
    binaryClf = binaryClf(class_weight='balanced').fit(X_train, y_train)
    # obtain class probabilities
    y_prob = binaryClf.predict_proba(X_test)[:, 1]

    # score based on roc auc
    score = roc_auc_score(y_test, y_prob)

    print("Binary classifier roc auc score: ", score)
    
    print("-"*40)
    print("\nTesting the MasterModel using the trained binaryClf and multiclassClf as well as the dictionary of known ransomware addresses")

    X = df[features]
    y = df.label

    X_train,X_test,y_train,y_test=train_test_split(X,y,test_size=0.25,random_state=0)

    master = MasterModel(dict_known_address, binaryClf, multiclassClf)


    preds = master.predictions(X_test)
    score = accuracy_score(y_test, preds)
    print("Master model score: ", score)
    
    

if __name__ == '__main__':
    
    try:
        raw_df_test = pd.read_csv('../DataHacks-2021/Intermediate Track 1 (Bitcoin)/Datasets/bitcoin_test.csv')
        raw_df = pd.read_csv('../DataHacks-2021/Intermediate Track 1 (Bitcoin)/Datasets/bitcoin_train.csv')
    except FileNotFoundError as e:
        print("\nERROR: DATASETS AREN'T IN ../DataHacks-2021/Intermediate Track 1 (Bitcoin)/Datasets/bitcoin_*.csv'\n")
        raise e

    main()