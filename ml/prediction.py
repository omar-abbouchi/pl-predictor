import pandas as pd
matches = pd.read_csv("ml/matches.csv", index_col=0)

#convert all objects to int or float to be processed by the ml software

matches["date"] = pd.to_datetime(matches["date"])
matches["h/a"] = matches["venue"].astype("category").cat.codes #convert venue to home (1) or away (0)
matches["opp"] = matches["opponent"].astype("category").cat.codes #convert opponents to a number
matches["hour"] = matches["time"].str.replace(":.+", "", regex=True).astype("int") #convert hours to number in case a team plays better at a certain time
matches["day"] = matches["date"].dt.dayofweek #convert day of week to a number

matches["target"] = (matches["result"] == "W").astype("int") #set a win to value of 1

from sklearn.ensemble import RandomForestClassifier #import ML for nonlinear data

rf = RandomForestClassifier(n_estimators = 100, min_samples_split=10, random_state=1)
train = matches[matches["date"] < '2022-01-01'] #set training set to matches before jan. 1, 2022
test = matches[matches["date"] > '2022-01-01'] #set test set to matches after jan 1, 2022
predictors = ["h/a", "opp", "hour", "day"]

rf.fit(train[predictors], train["target"])
RandomForestClassifier(min_samples_split = 10, n_estimators = 100, random_state = 1)
preds = rf.predict(test[predictors]) #make the prediction

from sklearn.metrics import accuracy_score
_acc = accuracy_score(test["target"], preds) #test accuracy

combined = pd.DataFrame(dict(actual=test["target"], prediction=preds))
pd.crosstab(index=combined["actual"], columns=combined["prediction"])

from sklearn.metrics import precision_score
precision_score(test["target"], preds)

grouped_matches = matches.groupby("team")
group = grouped_matches.get_group("Manchester United").sort_values("date")

def rolling_averages(group, cols, new_cols): #takes current form of a team into consideration
    group =  group.sort_values("date") #sort games by date so we can get latest matches
    rolling_stats = group[cols].rolling(3, closed='left').mean() #get last 3 matches
    group[new_cols] = rolling_stats
    group = group.dropna(subset=new_cols)
    return group

cols = ["gf", "ga", "sh", "sot", "dist", "fk", "pk", "pkatt"]
new_cols = [f"{c}_rolling" for c in cols] #create and dynamically name new columns w rolling avg values

rolling_averages(group, cols, new_cols)

matches_rolling = matches.groupby("team").apply(lambda x: rolling_averages(x, cols, new_cols))
matches_rolling = matches_rolling.droplevel('team')

matches_rolling.index = range(matches_rolling.shape[0]) 

def make_predictions(data, predictors):
    train = data[data["date"] < '2022-01-01']
    test = data[data["date"] > '2022-01-01']
    rf.fit(train[predictors], train["target"])
    preds = rf.predict(test[predictors]) #make prediction
    combined = pd.DataFrame(dict(actual=test["target"], prediction=preds), index=test.index)
    precision = precision_score(test["target"], preds)
    return combined, precision #return values for prediction

combined, precision = make_predictions(matches_rolling, predictors + new_cols)

combined = combined.merge(matches_rolling[["date", "team", "opponent", "result"]], left_index=True, right_index=True)

class MissingDict(dict): #class that inherits from dict
    __missing__ = lambda self, key: key #in case a team name is missing

map_vals = {
    "Brighton and Hove Albion" : "Brighton",
    "Manchester United" : "Manchester Utd",
    "Tottenham Hotspur" : "Tottenham",
    "West Ham United" : "West Ham",
    "Wolverhampton Wanderers" : "Wolves"
}
mapping = MissingDict(**map_vals)
mapping["West Ham United"]

combined["new_team"] = combined["team"].map(mapping)
merged = combined.merge(combined, left_on=["date", "new_team"], right_on=["date", "opponent"]) #find home and away predictions and merge them 
