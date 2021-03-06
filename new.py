#-*- coding:utf-8 -*-
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from functools import partial
from sklearn import neighbors
from sklearn.cross_validation import KFold
from sklearn import preprocessing 
from matplotlib import pylab
import time

def avgtimeperday(df):
    t=df['time']
    return t.max()-t.min()
def most_interest_object(group):
    return np.sum(group['object'].value_counts()>10)

def class_num(df):
    return np.size(df['object'].value_counts())

def distance(df):
    return df['time'].max()-df['time'].min()

def extract_features(data,log,label=None):
    data['date'] = data['time'].dt.date
    features = []
    g_enrollment_id = data.groupby('enrollment_id')
    if label is not None:
        features.append(label)
    visit = g_enrollment_id.size()
    v=pd.DataFrame({'enrollment_id':visit.index,'visit_time':visit.values})
    features.append(v)

    user_visit = log.groupby('username').size().reset_index().rename_axis({0:'user_visit'},axis=1)
    user_visit = pd.merge(log,user_visit,on='username',how='outer')
    user_visit = user_visit[['enrollment_id','user_visit']]
    user_visit = user_visit.groupby('enrollment_id').mean().reset_index()
    features.append(user_visit)

    day_span = g_enrollment_id.apply(distance)
    day_span = day_span.dt.days/visit
    day_span=day_span.reset_index().rename_axis({0:'day_span'},axis=1)
    features.append(day_span)

    last_mouth = data[data['time']>'2014-07-01T17:31:15']
    last_mouth_visit=last_mouth.groupby('enrollment_id').size()
    lmv=pd.DataFrame({'enrollment_id':last_mouth_visit.index,'last_mouth_visit':last_mouth_visit.values})
    features.append(lmv)

    #last_week = data[data['time']>'2014-07-24T17:31:15']
    #last_week_visit=last_week.groupby('enrollment_id').size()
    #lwv=pd.DataFrame({'enrollment_id':last_week_visit.index,'last_week_visit':last_week_visit.values})
    #features.append(lwv)

    lv = g_enrollment_id
    lv =lv.aggregate({'time':np.max})
    max = data['time'].max()
    lv=max-lv['time']
    lv=lv.dt.days
    lv = pd.DataFrame({'enrollment_id':lv.index,'last_visit':lv.values})
    features.append(lv)

    event = data.groupby(['enrollment_id','event']).size().unstack().fillna(0)
    event.reset_index(inplace=True)
    features.append(event[['enrollment_id','discussion','video','problem']])

    source = data.groupby(['enrollment_id','source']).size().unstack().fillna(0)
    source.reset_index(inplace=True)
    features.append(source)

    g = g_enrollment_id
    mic=g.apply(most_interest_object) #most_interest_class,object>10
    mic=pd.DataFrame({'enrollment_id':mic.index,'mic':mic.values})
    features.append(mic)

    c_num = g.apply(class_num)
    c_num=pd.DataFrame({'enrollment_id':c_num.index,'c_num':c_num.values})
    features.append(c_num)

    avg_second_per_day = data.groupby(['enrollment_id','date']).apply(avgtimeperday)
    avg_second_per_day = avg_second_per_day.dt.seconds
    avg_second_per_day = avg_second_per_day.groupby(axis=0,level=0).mean()
    avg_second_per_day=pd.DataFrame({'enrollment_id':avg_second_per_day.index,'avg_second_per_day':avg_second_per_day.values})
    features.append(avg_second_per_day)

    result = reduce(partial(pd.merge,on='enrollment_id',how='outer'),features)
    result = result.fillna(0)
    return result


def measure(clf_class,parameters,x,y,name,data_size=None, plot=False):
    print "开始测试..."
    start_time = time.time()
    if data_size is None:
        X = x
        Y = y
    else:
        X = x[:data_size]
        Y = y[:data_size]

    scores = []
    train_errors = []
    test_errors = []
    roc_auc = []

    precisions, recalls, thresholds = [], [], []
    cv = KFold(n=len(X),n_folds=2,shuffle=True)

    for train,test in cv:
        x_train,y_train = X[train],Y[train]
        x_test,y_test = X[test],Y[test]
        clf = clf_class(**parameters)
        #clf = neighbors.KNeighborsClassifier(n_neighbors=100)
        clf.fit(x_train,y_train)

        train_score = clf.score(x_train, y_train)
        test_score = clf.score(x_test, y_test)

        train_errors.append(1 - train_score)
        test_errors.append(1 - test_score)
        print "train_error =%f\ttest_error =%f\n" % (1-train_score,1-test_score)

        scores.append(test_score)
        proba = clf.predict_proba(x_test)
        roc_auc.append(roc_auc_score(y_test,proba[:,1]))

    print "测试完毕"
    print "%s use time %s" % (name,time.time()-start_time)
    print "Score Mean = %.5f\tStddev = %.5f" % (np.mean(scores),np.std(scores))
    print "auc Mean = %.5f\tauc Stddev = %.5f" % (np.mean(roc_auc),np.std(roc_auc))
    return np.mean(train_errors), np.mean(test_errors)

def train_sets(reproduct=False):
    print "读取训练数据..."
    if reproduct:
        data = pd.read_csv('../train/log_train.csv',parse_dates=[1])
        enroll_train = pd.read_csv('../train/enrollment_train.csv')
        truth_train = pd.read_csv('../train/truth_train.csv',names=['enrollment_id','drop'])
        log_train = pd.merge(data,enroll_train,on="enrollment_id",how="outer")
        enroll_train = pd.merge(enroll_train,truth_train,on="enrollment_id",how="outer")
        result = extract_features(data,log_train,label=truth_train)
        result.to_csv('features.csv')
    else:
        result = pd.read_csv('features.csv',index_col=0)
        #X = np.genfromtxt("features.csv")
        #Y = np.genfromtxt("labels.csv")
    print result
    X = result.ix[:,2:].values
    Y = result['drop'].real
    #X = preprocessing.normalize(X,axis=0)
#X = visit.real.reshape(len(visit),1)
    return X,Y




def test_sets():

    print "读取测试数据..."
    test = pd.read_csv('../test/log_test.csv',parse_dates=[1])

    enroll_test = pd.read_csv('../test/enrollment_test.csv')
    log_test = pd.merge(test,enroll_test,on="enrollment_id",how="outer")

    visit_test = test.groupby('enrollment_id').size()
    test_features = extract_features(test,log_test)
    X_predict = test_features.ix[:,1:].values
    return X_predict,visit_test

def gen_submission(clf_class,parameters,x,y,name):
    X,Y = x,y
    clf = clf_class(**parameters)
    print "在整个训练集上训练模型..."
    clf.fit(X,Y)
    print "开始预测..."
    X_predict,visit_test = test_sets()
    Y_predict = clf.predict_proba(X_predict)
    submission = np.vstack((visit_test.index.values,Y_predict[:,1])).transpose()

    import datetime
    np.savetxt('%s-%s.csv' % (name,datetime.datetime.now()),submission,fmt="%d,%f")
    print "结果写入result文件"


def plot_bias_variance(data_sizes, train_errors, test_errors, name, title):
    pylab.figure(num=None, figsize=(6, 5))
    pylab.ylim([0.0, 1.0])
    pylab.xlabel('Data set size')
    pylab.ylabel('Error')
    pylab.title("Bias-Variance for '%s'" % name)
    pylab.plot(
        data_sizes, test_errors, "--", data_sizes, train_errors, "b-", lw=1)
    pylab.legend(["train error", "test error"], loc="upper right")
    pylab.grid(True, linestyle='-', color='0.75')
    pylab.savefig("bv_" + name.replace(" ", "_") + ".png", bbox_inches="tight")

def bias_variance_analysis(clf_class, parameters,x,y, name):
    data_sizes = np.arange(1000, 10000, 1000)
    X,Y = x,y

    train_errors = []
    test_errors = []

    for data_size in data_sizes:
        train_error, test_error = measure(
            clf_class, parameters, X, Y, name, data_size=data_size)
        train_errors.append(train_error)
        test_errors.append(test_error)

    plot_bias_variance(data_sizes, train_errors, test_errors, name, "Bias-Variance for '%s'" % name)
    
if __name__ == '__main__':
    X,Y = train_sets()
    #bias_variance_analysis(neighbors.KNeighborsClassifier,{'n_neighbors':100},X,Y,'knn')
    measure(neighbors.KNeighborsClassifier,{'n_neighbors':100},X,Y,'knn')
    #gen_submission(neighbors.KNeighborsClassifier,{'n_neighbors':100},X,Y,'knn')

