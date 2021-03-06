import numpy as np
from GeneticSearch import GeneticSearch
from collections import namedtuple

SearchInterval = namedtuple('SearchInterval', ['low', 'high'])

class Config:
    numOfIntervalPartitions = 9
    maxNumOfImproveTries = 15
    populationSize = 150

class GeneticNN:
    """
    This class is intended to perform weight search for Neural Networks. Given the interval of values
    the weights / parameters should be in, it performs a genetic search by searching in a similar fashion to binary
    search for each weight / parameter.
    """



    def __init__(self, interval, config=Config(), logFile=None):
        """

        :param interval: a SearchInterval tuple of low and high interval boundaries - (low, high).
        :param logFile:
        """
        self.searchInterval = interval
        self.logFile = logFile
        self.config = config

    def tuneParameters(self, model, dataLabelGenerator, numberOfIterations=5, verbose=True):
        """
        This function should actually tune the parameters / weights and return a list of tuned parameters as result.
        :return:
        """
        parametersInfoList = model.getParametersInfoList()
        weightsSizesList = [p[1] for p in parametersInfoList]
        weightsShapesList = [p[0] for p in parametersInfoList]
        numberOfParameters = np.sum(weightsSizesList)

        #   Each weight is initialized to search a weight in the whole initial interval:
        searchIntervals = [self.searchInterval for i in range(numberOfParameters)]

        #   Start iterations to look for better weights:
        bestParams = None
        bestFitness = None
        bestPoint = None
        evaluator = NNWeightsEvaluator(searchIntervals, self.config.numOfIntervalPartitions,
                                       model, weightsShapesList, weightsSizesList, dataLabelGenerator)
        GA = GeneticSearch(numberOfParameters, self.logFile,
                               numOfCategories=self.config.numOfIntervalPartitions, fitnessObj=evaluator)
        for iteration in range(numberOfIterations):
            GA.constructPopulation(self.config.populationSize, GeneticSearch.InitialPopulation.RANDOM)
            GA.startEvolution(maxNumOfImproveTries=self.config.maxNumOfImproveTries , verbose=True)

            currentBestParams, currentBestFitness = GA.getBestSubsetAllTimes()
            currentBestPoint = self.getPoint(currentBestParams, searchIntervals, self.config.numOfIntervalPartitions)
            if bestFitness is None or currentBestFitness < bestFitness:
                bestParams = currentBestParams
                bestFitness = currentBestFitness
                bestPoint = currentBestPoint

            if verbose:
                self.log("Current Best Fitness: {}".format(currentBestFitness))
                self.log("Current Best Point: {}".format(currentBestPoint))

            #   Update the weights's search intervals based on the result:
            updatedSearchIntervals = [self.getSubInterval(interval, paramDir) \
                                     for interval, paramDir in zip(searchIntervals, currentBestParams)]
            searchIntervals = updatedSearchIntervals
            evaluator.updateSearchIntervals(searchIntervals)

        #   Update the model's parameters to the best found:
        model.updateParameters(evaluator.transformWeightVecToList(bestPoint))


    def getSubInterval(self, interval, subIntervalIdx):
        """

        :param interval:
        :param subintervalIdx:
        :return:
        """
        subIntervalDelta = (interval.high - interval.low) / float(self.config.numOfIntervalPartitions)
        low = interval.low + subIntervalIdx * subIntervalDelta
        high = low + subIntervalDelta
        return SearchInterval(low, high)


    @staticmethod
    def getPoint(individual, intervals, numOfIntervalPartitions):
        """
        Using the search intervals and individual (boolean vector), return the corresponding point they represents.
        :param numOfIntervalPartitions:
        :param individual: a boolean vector from the GA
        :param intervals: the vector of search intervals.
        :return: a point in space with value for each weight.
        """
        return np.array([GeneticNN.getValueInInterval(interval, side, numOfIntervalPartitions) \
                         for interval, side in zip(intervals, individual)])

    @staticmethod
    def getValueInInterval(interval, side, numOfIntervalPartitions):
        """
        Given an interval and a boolean side (represents top / bottom), return the value that represents the
        sub-interval (the middle).
        :param numOfIntervalPartitions:
        :param interval: a SearchInterval object - tuple of (low,high).
        :param side: boolean that represents the relevant sub-interval. false = lower, true = higher.
        :return: a number representing the relevant half (it's middle).
        """
        diff = interval.high - interval.low
        #   calculate the middle of the lower side (represent the lower interval):
        lowSide = interval.low + diff/(numOfIntervalPartitions * 2)
        #   calculate the value you need to add to get the middle of the higher side:
        lowToHighSide = diff / numOfIntervalPartitions

        #   return the right one using the boolean side:
        return lowSide + side * lowToHighSide

    def log(self, msg):
        print (msg)





class NNWeightsEvaluator:

    def __init__(self, searchIntervals, numOfIntervalPartitions, model,
                 weightsShapesList, weightsSizesList, dataLabelGenerator):
        self.searchIntervals = searchIntervals
        self.numOfIntervalPartitions = numOfIntervalPartitions
        self.model = model
        self.weightsShapesList = weightsShapesList
        self.weightsSizesList = weightsSizesList
        self.dataLabelGenerator = dataLabelGenerator

    def updateSearchIntervals(self, newSearchIntervals):
        self.searchIntervals = newSearchIntervals

    def evaluateFitness(self, individual):
        """
        This function should return the fitness of the individual for the genetic search
        :param individual:
        :return: value between 0 and 100. 0 = best, 100 = worst
        """
        weights = GeneticNN.getPoint(individual, self.searchIntervals, self.numOfIntervalPartitions)

        #   update model's weights, and get score:
        parametersList = self.transformWeightVecToList(weights)
        from NNFullyCon import NNFullyCon
        # self.model = NNFullyCon([10, 10, 10, 10])
        self.model.updateParameters(parametersList)

        #   compute score and transform to fitness:
        trainSet, trainLabels = self.dataLabelGenerator()
        modelScore = self.model.score(trainSet, trainLabels)
        #print(modelScore)
        modelCE = self.model.getCELoss(trainSet, trainLabels)
        #return (1 - modelScore) * 100
        return modelCE

    def transformWeightVecToList(self, weightsVec):
        """
        Given a 1-D vector of weights, return a list of weights as the model expects to get.
        :param weightsVec:
        :return:
        """
        curIdx = 0
        parametersList = []
        for wShape, wSize in zip(self.weightsShapesList, self.weightsSizesList):
            curWeight = np.reshape(weightsVec[curIdx : curIdx+wSize], wShape)
            curIdx += wSize
            parametersList.append(curWeight)
        return parametersList



class NNGeneticModel:
    """
    This is a template class for models that can make use of the GeneticNN weight update algorithm.
    """
    def getParametersList(self):
        """
        Return a list of parameters to tune (each one can be a np.array)
        :return:
        """
        raise NotImplementedError

    def updateParameters(self, parametersList):
        """
        Members of this class should be able to update their parameters given a list of them.
        :return:
        """
        raise NotImplementedError

    def score(self, testExamples, testLabels):
        """
        Return the error of the model on the given test
        :param testExamples:
        :param testLabels:
        :return:
        """
        raise NotImplementedError